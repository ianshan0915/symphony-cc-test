"""Adapter mapping deepagents / LangGraph streaming events → SSE format.

The adapter translates two LangGraph ``astream()`` stream modes into the SSE
event vocabulary expected by the frontend (``ChatInterface.tsx``):

* **messages** mode → ``token``, ``tool_call`` SSE events
* **updates** mode → ``tool_result`` SSE events, plus interrupt detection

V2 streaming with ``subgraphs=True`` adds a namespace (``ns``) field to
events, enabling detection of subagent execution.  Subagent events are
mapped to ``sub_agent_start``, ``sub_agent_progress``, and
``sub_agent_end`` SSE events consumed by the frontend's
``SubAgentProgress.tsx`` component.

This module is intentionally stateless — all state lives in
:class:`~app.services.agent_service.AgentService`.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.services.sse import SSEEvent

logger = logging.getLogger(__name__)


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
                events.append(
                    SSEEvent(
                        event="tool_result",
                        data={
                            "run_id": getattr(msg, "tool_call_id", ""),
                            "output": str(msg.content)[:2000],
                        },
                    )
                )

    return events


# ---------------------------------------------------------------------------
# Interrupt extraction
# ---------------------------------------------------------------------------


def extract_interrupt(update: dict[str, Any]) -> dict[str, Any] | None:
    """Extract interrupt data from a LangGraph *updates*-mode payload.

    When a deepagents tool calls ``interrupt()``, the updates stream
    yields a special ``__interrupt__`` key containing the interrupt value.

    Returns
    -------
    dict | None
        The interrupt payload (tool_name, tool_args, etc.) or ``None``
        if the update does not represent an interrupt.
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
    if name in ("tools", "__interrupt__", "agent"):
        return None

    return name if name else None
