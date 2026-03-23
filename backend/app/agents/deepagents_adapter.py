"""Adapter mapping deepagents / LangGraph streaming events → SSE format.

The adapter translates two LangGraph ``astream()`` stream modes into the SSE
event vocabulary expected by the frontend (``ChatInterface.tsx``):

* **messages** mode → ``token``, ``tool_call`` SSE events
* **updates** mode → ``tool_result``, ``todo_update`` SSE events, plus interrupt detection

V2 streaming with ``subgraphs=True`` adds a namespace (``ns``) field to
events, enabling detection of subagent execution.  Subagent events are
mapped to ``sub_agent_start``, ``sub_agent_progress``, and
``sub_agent_end`` SSE events consumed by the frontend's
``SubAgentProgress.tsx`` component.

This module is intentionally stateless — all state lives in
:class:`~app.services.agent_service.AgentService`.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from typing import Any, Literal

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app.services.sse import SSEEvent

logger = logging.getLogger(__name__)

# LangGraph injects interrupt data under this reserved key in updates-mode payloads.
_INTERRUPT_KEY = "__interrupt__"

# Valid planning-tool status values surfaced via ``todo_update`` SSE events.
TodoStatus = Literal["pending", "in_progress", "completed"]

# Native filesystem tool names provided by deepagents when a backend is
# configured.  Used to emit ``file_event`` SSE events alongside the
# standard ``tool_result`` so the frontend can render file operations.
_FILESYSTEM_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ls",
        "read_file",
        "write_file",
        "create_file",
        "edit_file",
        "glob",
        "grep",
        "execute",
    }
)

# Tools that produce artifacts (files with user-visible content).
_ARTIFACT_WRITE_TOOLS: frozenset[str] = frozenset(
    {"write_file", "create_file", "edit_file"}
)

# File extensions that should be auto-detected as artifacts when produced
# by code execution.  These are "viewable" formats the frontend can render.
_EXECUTE_ARTIFACT_EXTENSIONS: frozenset[str] = frozenset(
    {".html", ".htm", ".svg", ".csv", ".json", ".md"}
)

# Maximum file size (bytes) to inline as an artifact from execute output.
# Larger files are skipped to avoid bloating the SSE stream.
_EXECUTE_ARTIFACT_MAX_SIZE: int = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Execute result parsing
# ---------------------------------------------------------------------------


def _parse_execute_result(content: str) -> dict[str, Any]:
    """Parse the output of the ``execute`` tool into structured fields.

    deepagents' LocalShellBackend returns execute results as either a JSON
    object or a plain-text representation.  This function normalises both
    formats into a dict with ``stdout``, ``stderr``, and ``exit_code`` keys.

    Falls back gracefully: if parsing fails the raw content is returned as
    ``stdout`` with an empty ``stderr`` and ``exit_code`` of ``-1``.

    Parameters
    ----------
    content:
        The string content of the ``ToolMessage`` for an ``execute`` call.

    Returns
    -------
    dict[str, Any]
        ``{"stdout": str, "stderr": str, "exit_code": int}``
    """
    import json
    import re

    # Try JSON first — deepagents may return a JSON-serialised dict.
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            raw_exit = parsed.get("exit_code", parsed.get("returncode", 0))
            return {
                "stdout": str(parsed.get("stdout", "")),
                "stderr": str(parsed.get("stderr", "")),
                # Preserve an explicit 0 exit code (falsy but valid).
                # Only fall back to 0 when the key is absent (None).
                "exit_code": int(raw_exit) if raw_exit is not None else 0,
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # Try plain-text format: "Exit code: N\nstdout:\n...\nstderr:\n..."
    # or variations thereof produced by different backends.
    exit_code = 0
    exit_match = re.search(r"(?i)exit\s*code[:\s]+(-?\d+)", content)
    if exit_match:
        with contextlib.suppress(ValueError):
            exit_code = int(exit_match.group(1))

    stdout = ""
    stderr = ""

    stdout_match = re.search(r"(?i)stdout[:\s]*(.*?)(?=stderr[:\s]|$)", content, re.DOTALL)
    if stdout_match:
        stdout = stdout_match.group(1).strip()

    stderr_match = re.search(r"(?i)stderr[:\s]*(.*?)$", content, re.DOTALL)
    if stderr_match:
        stderr = stderr_match.group(1).strip()

    # If no structured markers were found, treat the whole content as stdout.
    if not stdout and not stderr:
        stdout = content.strip()

    return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}


# ---------------------------------------------------------------------------
# Execute artifact scanner
# ---------------------------------------------------------------------------

# Track files already emitted as artifacts (by mtime) to avoid duplicates
# across multiple execute calls in the same session.
_emitted_artifact_files: dict[str, float] = {}


def _scan_execute_artifacts(run_id: str) -> list[SSEEvent]:
    """Scan the sandbox workspace for output files produced by code execution.

    After a successful ``execute`` tool call, this function checks the sandbox
    workspace directory for recently created/modified files with viewable
    extensions (e.g. ``.html``, ``.svg``, ``.csv``).  For each new file found,
    an ``artifact_created`` SSE event is emitted so the frontend can display
    them in the artifact panel.

    This bridges the gap between files written via ``write_file`` (which already
    produce artifacts) and files generated as side effects of code execution
    (e.g. a Python script that generates an HTML dashboard).

    Parameters
    ----------
    run_id:
        The run_id of the execute tool call, used to tag the artifact events.

    Returns
    -------
    list[SSEEvent]
        Zero or more ``artifact_created`` events for newly detected files.
    """
    from app.config import settings

    workspace = settings.sandbox_workspace_dir
    if not os.path.isdir(workspace):
        return []

    events: list[SSEEvent] = []
    now = time.time()
    # Only consider files modified within the last 60 seconds
    recency_threshold = 60.0

    try:
        for entry in os.scandir(workspace):
            if not entry.is_file():
                continue

            _, ext = os.path.splitext(entry.name.lower())
            if ext not in _EXECUTE_ARTIFACT_EXTENSIONS:
                continue

            try:
                stat = entry.stat()
            except OSError:
                continue

            # Skip files that are too old (not from this execution)
            if now - stat.st_mtime > recency_threshold:
                continue

            # Skip files that are too large
            if stat.st_size > _EXECUTE_ARTIFACT_MAX_SIZE:
                logger.debug(
                    "Skipping large execute artifact %s (%d bytes)",
                    entry.name,
                    stat.st_size,
                )
                continue

            # Skip files we've already emitted (same path and mtime)
            prev_mtime = _emitted_artifact_files.get(entry.path)
            if prev_mtime is not None and prev_mtime >= stat.st_mtime:
                continue

            # Read the file content
            try:
                with open(entry.path, encoding="utf-8", errors="replace") as f:
                    file_content = f.read()
            except OSError:
                continue

            _emitted_artifact_files[entry.path] = stat.st_mtime

            events.append(
                SSEEvent(
                    event="artifact_created",
                    data={
                        "run_id": run_id,
                        "tool_name": "execute",
                        "file_path": entry.name,
                        "content": file_content,
                    },
                )
            )
            logger.info(
                "Execute artifact detected: %s (%d bytes)",
                entry.name,
                stat.st_size,
            )

    except OSError:
        logger.debug("Failed to scan sandbox workspace for execute artifacts", exc_info=True)

    return events


# ---------------------------------------------------------------------------
# Message-mode mapping
# ---------------------------------------------------------------------------


def map_message_chunk(
    chunk: Any,
    metadata: dict[str, Any],
) -> list[SSEEvent]:
    """Map a LangGraph *messages*-mode chunk to zero or more SSE events.

    Parameters
    ----------
    chunk:
        Typically an :class:`AIMessageChunk` with ``.content`` and/or
        ``.tool_call_chunks``.
    metadata:
        Streaming metadata dict (e.g. ``{"langgraph_node": "agent"}``).

    Returns
    -------
    list[SSEEvent]
        SSE events derived from the chunk.  May be empty if the chunk
        carries no user-visible payload (e.g. an empty token).
    """
    if not isinstance(chunk, AIMessageChunk):
        return []

    events: list[SSEEvent] = []

    # --- Token content ---
    if chunk.content and isinstance(chunk.content, str):
        events.append(SSEEvent(event="token", data={"token": chunk.content}))

    # --- Tool-call chunks (streamed incrementally) ---
    if getattr(chunk, "tool_call_chunks", None):
        for tc in chunk.tool_call_chunks:
            # Only emit on the *first* chunk of a tool call (has a name)
            name = tc.get("name")
            if name:
                events.append(
                    SSEEvent(
                        event="tool_call",
                        data={
                            "tool_name": name,
                            "tool_input": tc.get("args", {}),
                            "run_id": tc.get("id", ""),
                        },
                    )
                )

    return events


# ---------------------------------------------------------------------------
# Updates-mode mapping
# ---------------------------------------------------------------------------


def map_state_update(
    update: dict[str, Any],
    pending_tool_calls: dict[str, dict[str, Any]] | None = None,
) -> list[SSEEvent]:
    """Map a LangGraph *updates*-mode payload to zero or more SSE events.

    Handles two event types:

    * **Tool results** — ``ToolMessage`` objects present in node outputs.
    * **Context summarization** — when ``SummarizationMiddleware`` compresses
      the conversation history a ``_summarization_event`` key appears in the
      node's state update.  We surface this as a ``context_summarized`` SSE
      event so the frontend can display a "conversation was summarised" notice.

    Parameters
    ----------
    update:
        A dict of ``{node_name: state_update}`` pairs yielded by
        ``astream(stream_mode="updates")``.

    Returns
    -------
    list[SSEEvent]
        SSE events — typically ``tool_result`` and/or ``context_summarized``.
    """
    events: list[SSEEvent] = []

    for node_name, node_output in update.items():
        if node_name == _INTERRUPT_KEY:
            continue  # handled separately by extract_interrupt()

        messages: list[Any] = []
        if isinstance(node_output, dict):
            raw_messages = node_output.get("messages", [])
            # deepagents may wrap messages in a LangGraph ``Overwrite``
            # container (e.g. ``Overwrite(value=[...])``) when replacing
            # state.  Unwrap to get the underlying list.
            if hasattr(raw_messages, "value"):
                messages = raw_messages.value if isinstance(raw_messages.value, list) else []
            elif isinstance(raw_messages, list):
                messages = raw_messages
            else:
                messages = []

            # Detect a summarization event emitted by SummarizationMiddleware.
            # The middleware stores the event under the private state key
            # ``_summarization_event`` when it compresses the conversation
            # history.  We emit a ``context_summarized`` SSE so the frontend
            # can indicate that older context has been compressed.
            summ_event: dict[str, Any] | None = node_output.get("_summarization_event")
            if summ_event and isinstance(summ_event, dict):
                file_path: str | None = summ_event.get("file_path")
                cutoff_index: int | None = summ_event.get("cutoff_index")
                events.append(
                    SSEEvent(
                        event="context_summarized",
                        data={
                            "node": node_name,
                            "cutoff_index": cutoff_index,
                            "history_file": file_path,
                        },
                    )
                )
                logger.info(
                    "Context summarized at node=%s cutoff=%s history=%s",
                    node_name,
                    cutoff_index,
                    file_path,
                )

        elif isinstance(node_output, list):
            messages = node_output

        # Accumulate tool_call_id → args from AIMessages across updates.
        # AIMessages with tool_calls appear in the "agent" node update,
        # while the corresponding ToolMessages appear later in the "tools"
        # node update.  By accumulating into `pending_tool_calls` we can
        # look up the original args when processing tool results.
        if pending_tool_calls is None:
            pending_tool_calls = {}
        for msg in messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    tc_id = tc.get("id", "")
                    if tc_id:
                        pending_tool_calls[tc_id] = tc.get("args", {})

        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = str(msg.content)
                tool_name = getattr(msg, "name", None) or ""
                run_id = getattr(msg, "tool_call_id", "")

                # Emit file_event for native filesystem tool results so the
                # frontend can render file operations inline.
                if tool_name in _FILESYSTEM_TOOL_NAMES:
                    events.append(
                        SSEEvent(
                            event="file_event",
                            data={
                                "run_id": run_id,
                                "tool_name": tool_name,
                                "output": content,
                            },
                        )
                    )

                # For the execute tool, emit a structured execute_result event
                # with parsed stdout, stderr, and exit_code so the frontend can
                # display code-execution output with proper formatting.
                if tool_name == "execute":
                    parsed = _parse_execute_result(content)
                    events.append(
                        SSEEvent(
                            event="execute_result",
                            data={
                                "run_id": run_id,
                                "stdout": parsed["stdout"],
                                "stderr": parsed["stderr"],
                                "exit_code": parsed["exit_code"],
                            },
                        )
                    )

                    # Scan the sandbox workspace for output files produced by
                    # the execute command (e.g. HTML dashboards, CSV exports).
                    # Only emit artifacts for successful executions.
                    if parsed.get("exit_code", -1) == 0:
                        for artifact_event in _scan_execute_artifacts(run_id):
                            events.append(artifact_event)

                # With CompositeBackend, deepagents offloads large tool
                # outputs to the filesystem automatically (returning a
                # pointer instead of inline content).  The blunt 2K
                # truncation is therefore no longer needed.
                events.append(
                    SSEEvent(
                        event="tool_result",
                        data={
                            "run_id": run_id,
                            "output": content,
                        },
                    )
                )

                # For artifact-producing tools (write/create/edit), emit an
                # ``artifact_created`` event with the file path and content
                # so the frontend can display the artifact in the panel.
                if tool_name in _ARTIFACT_WRITE_TOOLS:
                    original_args = pending_tool_calls.get(run_id, {})
                    file_path = (
                        original_args.get("file_path")
                        or original_args.get("path")
                        or ""
                    )
                    file_content = (
                        original_args.get("content")
                        or original_args.get("new_content")
                        or original_args.get("text")
                        or ""
                    )
                    if file_path and file_content:
                        events.append(
                            SSEEvent(
                                event="artifact_created",
                                data={
                                    "run_id": run_id,
                                    "tool_name": tool_name,
                                    "file_path": file_path,
                                    "content": file_content,
                                },
                            )
                        )

    return events


# ---------------------------------------------------------------------------
# Todo update mapping
# ---------------------------------------------------------------------------


def map_todo_update(update: dict[str, Any]) -> list[SSEEvent]:
    """Map a LangGraph *updates*-mode payload to ``todo_update`` SSE events.

    Detects ``write_todos`` tool calls by inspecting state updates for a
    ``todos`` key, which is populated whenever the agent calls the built-in
    ``write_todos`` planning tool (provided by ``TodoListMiddleware``).

    The ``write_todos`` tool stores its input directly in the graph state as
    ``todos: list[Todo]``, where each ``Todo`` has ``content`` and ``status``
    fields.  This function maps those to the frontend-facing format:

    .. code-block:: json

        {
          "event": "todo_update",
          "data": {
            "todos": [
              {"id": "1", "description": "Research API options", "status": "completed"},
              {"id": "2", "description": "Write implementation", "status": "in_progress"},
              {"id": "3", "description": "Add tests", "status": "pending"}
            ]
          }
        }

    Parameters
    ----------
    update:
        A dict of ``{node_name: state_update}`` pairs yielded by
        ``astream(stream_mode="updates")``.

    Returns
    -------
    list[SSEEvent]
        ``todo_update`` SSE events if a ``write_todos`` call is detected,
        otherwise an empty list.
    """
    events: list[SSEEvent] = []

    for node_name, node_output in update.items():
        if node_name == _INTERRUPT_KEY:
            continue

        if not isinstance(node_output, dict):
            continue

        todos_raw = node_output.get("todos")
        if not isinstance(todos_raw, list):
            continue

        # Map Todo TypedDicts ({content, status}) → frontend format ({id, description, status}).
        # Index-based IDs (1-based) are stable for a given write_todos call and sufficient
        # for the frontend to render the list — the agent replaces the entire list each call.
        todos = [
            {
                "id": str(i + 1),
                "description": item.get("content", "") if isinstance(item, dict) else str(item),
                "status": item.get("status", "pending") if isinstance(item, dict) else "pending",
            }
            for i, item in enumerate(todos_raw)
        ]
        events.append(SSEEvent(event="todo_update", data={"todos": todos}))

    return events


# ---------------------------------------------------------------------------
# Interrupt extraction
# ---------------------------------------------------------------------------


def extract_interrupt(update: dict[str, Any]) -> dict[str, Any] | None:
    """Extract interrupt data from a LangGraph *updates*-mode payload.

    When deepagents' native ``interrupt_on`` fires (or a tool manually calls
    ``interrupt()``), the updates stream yields a special ``__interrupt__``
    key containing the interrupt value.

    The returned dict is normalised to always contain at least
    ``tool_name`` and ``tool_args``.  Native ``interrupt_on`` payloads may
    also carry ``allowed_decisions``.

    Returns
    -------
    dict | None
        The interrupt payload (tool_name, tool_args, allowed_decisions, etc.)
        or ``None`` if the update does not represent an interrupt.
    """
    interrupts = update.get(_INTERRUPT_KEY)
    if not interrupts:
        return None

    # Take the first interrupt (multiple simultaneous interrupts are rare)
    interrupt_obj = interrupts[0]

    # langgraph.types.Interrupt has a `.value` attribute
    if hasattr(interrupt_obj, "value"):
        value = interrupt_obj.value
    elif isinstance(interrupt_obj, dict):
        value = interrupt_obj
    else:
        value = {"data": interrupt_obj}

    if not isinstance(value, dict):
        value = {"data": value}

    # HumanInTheLoopMiddleware emits HITLRequest with action_requests and
    # review_configs.  Normalise to the tool_name/tool_args format expected
    # by the SSE layer.
    #
    # IMPORTANT: The LLM may generate *multiple* tool calls in a single turn
    # that all require approval.  We must track ALL of them so the resume
    # command sends back one decision per tool call (the middleware enforces
    # decisions.length == action_requests.length).
    action_requests = value.get("action_requests")
    if action_requests and isinstance(action_requests, list) and len(action_requests) > 0:
        first_action = action_requests[0]
        tool_name = first_action.get("name", "unknown")
        tool_args = first_action.get("args", {})
        # Extract allowed_decisions from review_configs
        review_configs = value.get("review_configs", [])
        allowed_decisions = (
            review_configs[0].get("allowed_decisions", ["approve", "reject"])
            if review_configs
            else ["approve", "reject"]
        )
        # Build per-action list so the resume handler can generate one
        # decision per pending tool call.
        all_actions = [
            {
                "name": ar.get("name", "unknown"),
                "args": ar.get("args", {}),
            }
            for ar in action_requests
        ]
        return {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "allowed_decisions": allowed_decisions,
            "action_requests": all_actions,
            "action_count": len(all_actions),
        }

    return value


# ---------------------------------------------------------------------------
# Structured response extraction
# ---------------------------------------------------------------------------


def extract_structured_response(update: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the structured response payload from a LangGraph *updates*-mode chunk.

    When an agent is created with ``response_format`` set, deepagents stores
    the validated Pydantic instance (serialised as a dict) in the LangGraph
    state under the ``structured_response`` key.  This function scans each
    node's output for that key and returns the first non-``None`` value found.

    Parameters
    ----------
    update:
        A dict of ``{node_name: state_update}`` pairs yielded by
        ``astream(stream_mode="updates")``.

    Returns
    -------
    dict | None
        The serialised structured response (as a plain dict) if present in
        any node's output, otherwise ``None``.
    """
    for node_name, node_output in update.items():
        if node_name == _INTERRUPT_KEY:
            continue

        if not isinstance(node_output, dict):
            continue

        structured = node_output.get("structured_response")
        if structured is None:
            continue

        # deepagents may store a Pydantic model instance or an already-serialised dict.
        if hasattr(structured, "model_dump"):
            # Pydantic v2
            return structured.model_dump()  # type: ignore[union-attr]
        if hasattr(structured, "dict"):
            # Pydantic v1 fallback
            return structured.dict()  # type: ignore[union-attr]
        if isinstance(structured, dict):
            return structured

        # Coerce any other type to a dict-compatible representation
        return {"value": structured}

    return None


# ---------------------------------------------------------------------------
# Subagent namespace extraction
# ---------------------------------------------------------------------------


def extract_subagent_namespace(ns: tuple[str, ...] | None) -> str | None:
    """Extract the subagent name from a V2 streaming namespace tuple.

    In V2 streaming with ``subgraphs=True``, events from subagents carry
    a namespace tuple like ``("researcher:abc123",)`` where the prefix
    before the colon is the subagent name.  Supervisor-level events have
    an empty or ``None`` namespace.

    Parameters
    ----------
    ns:
        The namespace tuple from a V2 streaming event, or ``None``.

    Returns
    -------
    str | None
        The subagent name (e.g. ``"researcher"``) or ``None`` if the
        event is from the supervisor.
    """
    if not ns:
        return None

    # The namespace is typically a tuple of strings like ("researcher:abc123",)
    # or ("tools:abc123",).  We extract the name prefix before the colon.
    first = ns[0]
    if not isinstance(first, str):
        return None

    # Extract the subagent name (part before the colon or the full string)
    name = first.split(":")[0] if ":" in first else first

    # Skip internal LangGraph node names that aren't subagents
    if name in ("tools", _INTERRUPT_KEY, "agent"):
        return None

    return name if name else None
