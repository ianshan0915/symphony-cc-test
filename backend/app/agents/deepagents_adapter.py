"""Adapter mapping deepagents / LangGraph streaming events → SSE format.

The adapter translates two LangGraph ``astream()`` stream modes into the SSE
event vocabulary expected by the frontend (``ChatInterface.tsx``):

* **messages** mode → ``token``, ``tool_call`` SSE events
* **updates** mode → ``tool_result`` SSE events, plus interrupt detection

Filesystem events from native filesystem tools (backed by
``CompositeBackend``) are also mapped to ``file_event`` SSE events so the
frontend can display file operations inline.

This module is intentionally stateless — all state lives in
:class:`~app.services.agent_service.AgentService`.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.services.sse import SSEEvent

logger = logging.getLogger(__name__)

# Native filesystem tool names provided by deepagents when a backend is
# configured.  Used to emit ``file_event`` SSE events alongside the
# standard ``tool_result`` so the frontend can render file operations.
_FILESYSTEM_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "execute",
    }
)


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


def map_state_update(update: dict[str, Any]) -> list[SSEEvent]:
    """Map a LangGraph *updates*-mode payload to zero or more SSE events.

    Primarily used to capture **tool results** from ``ToolMessage`` objects
    present in node outputs.

    Parameters
    ----------
    update:
        A dict of ``{node_name: state_update}`` pairs yielded by
        ``astream(stream_mode="updates")``.

    Returns
    -------
    list[SSEEvent]
        SSE events — typically ``tool_result`` events.
    """
    events: list[SSEEvent] = []

    for node_name, node_output in update.items():
        if node_name == "__interrupt__":
            continue  # handled separately by extract_interrupt()

        messages: list[Any] = []
        if isinstance(node_output, dict) and "messages" in node_output:
            messages = node_output["messages"]
        elif isinstance(node_output, list):
            messages = node_output

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
    interrupts = update.get("__interrupt__")
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

    return value
