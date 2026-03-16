"""Agent service — manages agent lifecycle, thread state, and streaming.

Uses deepagents' ``astream()`` API with dual stream modes (``messages`` +
``updates``) and its built-in ``interrupt`` mechanism for human-in-the-loop
approval flows.

When the agent invokes a tool listed in ``TOOLS_REQUIRING_APPROVAL``, the
graph is configured to interrupt *before* that tool node executes.  The
stream emits an ``approval_required`` SSE event and waits for the caller
to resolve the decision.  On approval the graph is resumed with
``Command(resume=True)``; on rejection it is resumed with
``Command(resume=False)`` so the agent can handle the refusal gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.agents.deepagents_adapter import (
    extract_interrupt,
    extract_subagent_namespace,
    map_message_chunk,
    map_state_update,
)
from app.agents.factory import create_deep_agent
from app.models.thread import Thread
from app.services.sse import SSEEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration — tools that require human approval before execution
# ---------------------------------------------------------------------------

TOOLS_REQUIRING_APPROVAL: set[str] = {
    "web_search",
    "search_knowledge_base",
    # Add tool names here that should pause for user approval
}


# ---------------------------------------------------------------------------
# Pending approval state
# ---------------------------------------------------------------------------


@dataclass
class PendingApproval:
    """Represents a tool call waiting for user approval."""

    approval_id: str
    thread_id: str
    tool_name: str
    tool_args: dict[str, Any]
    run_id: str
    # Event to signal when the user has made a decision
    decision_event: asyncio.Event = field(default_factory=asyncio.Event)
    # The user's decision — set before signalling the event
    approved: bool | None = None
    reject_reason: str | None = None


# ---------------------------------------------------------------------------
# Agent service
# ---------------------------------------------------------------------------


class AgentService:
    """Manages agent creation, invocation, and SSE event streaming.

    Holds a singleton agent graph (compiled once at startup) and provides
    a streaming interface that yields SSE events for each step of the agent
    execution.  Supports human-in-the-loop approval via deepagents'
    ``interrupt`` mechanism.
    """

    def __init__(self, agent: CompiledStateGraph | None = None) -> None:  # type: ignore[type-arg]
        self._agent = agent
        # Map of thread_id -> PendingApproval for active approval requests
        self._pending_approvals: dict[str, PendingApproval] = {}

    @property
    def agent(self) -> CompiledStateGraph:  # type: ignore[type-arg]
        """Return the default agent graph, creating one lazily if needed."""
        if self._agent is None:
            self._agent = create_deep_agent()
        return self._agent

    def get_agent(self, assistant_type: str | None = None) -> CompiledStateGraph:  # type: ignore[type-arg]
        """Return an agent for the given assistant type.

        If *assistant_type* is ``None`` or ``"general"``, returns the default
        singleton agent. Specialized types create a new agent with the
        appropriate prompt and tool configuration.
        """
        if not assistant_type or assistant_type == "general":
            return self.agent
        return create_deep_agent(assistant_type=assistant_type)

    def set_agent(self, agent: CompiledStateGraph) -> None:  # type: ignore[type-arg]
        """Replace the current agent graph (useful for testing)."""
        self._agent = agent

    # ------------------------------------------------------------------
    # Approval management
    # ------------------------------------------------------------------

    def get_pending_approval(self, thread_id: str) -> PendingApproval | None:
        """Return the pending approval for a thread, if any."""
        return self._pending_approvals.get(thread_id)

    async def resolve_approval(
        self,
        thread_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> bool:
        """Resolve a pending approval for the given thread.

        Returns True if an approval was found and resolved, False otherwise.
        """
        pending = self._pending_approvals.get(thread_id)
        if pending is None:
            return False

        pending.approved = approved
        pending.reject_reason = reason
        pending.decision_event.set()
        return True

    # ------------------------------------------------------------------
    # Streaming helpers
    # ------------------------------------------------------------------

    async def _stream_agent(
        self,
        active_agent: CompiledStateGraph,  # type: ignore[type-arg]
        agent_input: Any,
        config: dict[str, Any],
    ) -> AsyncIterator[tuple[str, Any, tuple[str, ...] | None]]:
        """Iterate over agent ``astream()`` with V2 streaming and subgraph support.

        Yields ``(mode, chunk, namespace)`` triples where *mode* is
        ``"messages"`` or ``"updates"``, *chunk* is the raw LangGraph
        payload, and *namespace* is the subagent namespace tuple (or
        ``None`` for supervisor-level events).

        V2 streaming with ``subgraphs=True`` emits events from both
        the supervisor and its subagents.  The ``ns`` field on each
        event identifies which subagent produced it (e.g.
        ``("researcher:abc123",)``).
        """
        async for event in active_agent.astream(
            agent_input,
            config=config,  # type: ignore[call-overload]
            stream_mode=["messages", "updates"],
            subgraphs=True,
            version="v2",
        ):
            # V2 events have an `ns` attribute for the subagent namespace
            ns: tuple[str, ...] | None = getattr(event, "ns", None)

            # V2 events also carry `mode` and `data` attributes
            if hasattr(event, "event") and hasattr(event, "data"):
                mode = event.event  # type: ignore[union-attr]
                chunk = event.data  # type: ignore[union-attr]
                yield (mode, chunk, ns)
            elif isinstance(event, tuple) and len(event) == 2:
                # Fallback for v1-style (mode, payload) tuples
                mode_str, payload = event
                yield (str(mode_str), payload, ns)
            else:
                yield ("updates", event, None)

    # ------------------------------------------------------------------
    # Main streaming interface
    # ------------------------------------------------------------------

    async def stream_response(
        self,
        *,
        thread_id: str,
        user_message: str,
        thread: Thread | None = None,
        assistant_type: str | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Stream agent response as SSE events.

        Uses deepagents' ``astream()`` with dual stream modes (``messages``
        for token/tool_call events, ``updates`` for tool_result events and
        interrupt detection).

        Parameters
        ----------
        thread_id:
            Unique thread identifier for conversation state.
        user_message:
            The user's input message.
        thread:
            Optional Thread ORM object for metadata.
        assistant_type:
            Agent specialization type (``"researcher"``, ``"coder"``,
            ``"writer"``, or ``"general"``).

        Yields events in order:
        1. ``message_start`` — signals the beginning of an assistant turn.
        2. ``token`` — each incremental text token from the LLM.
        3. ``tool_call`` — when the agent invokes a tool.
        4. ``approval_required`` — when an interrupt requests human approval.
        5. ``approval_result`` — after the user approves/rejects.
        6. ``tool_result`` — tool execution result.
        7. ``message_end`` — signals the end of the assistant turn with the
           full message content.

        On error an ``error`` event is yielded and the stream terminates.
        """
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        agent_input: Any = {"messages": [HumanMessage(content=user_message)]}

        # Select the appropriate agent for the assistant type
        active_agent = self.get_agent(assistant_type)

        # Emit message_start
        yield SSEEvent(
            event="message_start",
            data={"thread_id": thread_id, "assistant_type": assistant_type or "general"},
        )

        full_content = ""
        tool_calls_data: list[dict[str, Any]] = []
        # Track active subagent namespaces to emit start/end events
        active_subagents: set[str] = set()

        try:
            # Stream with potential interrupt/resume loop
            while True:
                interrupt_data: dict[str, Any] | None = None

                async for mode, chunk, ns in self._stream_agent(active_agent, agent_input, config):
                    # Detect subagent namespace and emit lifecycle events
                    subagent_name = extract_subagent_namespace(ns) if ns else None
                    if subagent_name and subagent_name not in active_subagents:
                        active_subagents.add(subagent_name)
                        yield SSEEvent(
                            event="sub_agent_start",
                            data={
                                "subagent_name": subagent_name,
                                "thread_id": thread_id,
                            },
                        )

                    if mode == "messages":
                        # chunk is a (message, metadata) tuple in messages mode
                        if isinstance(chunk, tuple) and len(chunk) == 2:
                            msg_chunk, metadata = chunk
                        else:
                            msg_chunk, metadata = chunk, {}

                        for sse_event in map_message_chunk(msg_chunk, metadata):
                            if subagent_name:
                                # Tag subagent events with progress type
                                yield SSEEvent(
                                    event="sub_agent_progress",
                                    data={
                                        "subagent_name": subagent_name,
                                        "thread_id": thread_id,
                                        "inner_event": sse_event.event,
                                        **sse_event.data,
                                    },
                                )
                            else:
                                if sse_event.event == "token":
                                    full_content += sse_event.data.get("token", "")
                                elif sse_event.event == "tool_call":
                                    tool_calls_data.append(sse_event.data)
                                yield sse_event

                    elif mode == "updates":
                        # Check for interrupt (human-in-the-loop)
                        if isinstance(chunk, dict):
                            interrupt_data = extract_interrupt(chunk)
                            for sse_event in map_state_update(chunk):
                                if subagent_name:
                                    yield SSEEvent(
                                        event="sub_agent_progress",
                                        data={
                                            "subagent_name": subagent_name,
                                            "thread_id": thread_id,
                                            "inner_event": sse_event.event,
                                            **sse_event.data,
                                        },
                                    )
                                else:
                                    yield sse_event

                # Emit sub_agent_end for any active subagents
                for sa_name in active_subagents:
                    yield SSEEvent(
                        event="sub_agent_end",
                        data={
                            "subagent_name": sa_name,
                            "thread_id": thread_id,
                        },
                    )
                active_subagents.clear()

                # If no interrupt, we're done streaming
                if interrupt_data is None:
                    break

                # --- Handle interrupt (approval flow) ---
                tool_name = interrupt_data.get("tool_name", "unknown")
                tool_args = interrupt_data.get("tool_args", {})
                run_id = interrupt_data.get("run_id", "")
                approval_id = str(uuid.uuid4())

                pending = PendingApproval(
                    approval_id=approval_id,
                    thread_id=thread_id,
                    tool_name=tool_name,
                    tool_args=tool_args if isinstance(tool_args, dict) else {"input": tool_args},
                    run_id=run_id,
                )
                self._pending_approvals[thread_id] = pending

                # Emit approval_required event
                yield SSEEvent(
                    event="approval_required",
                    data={
                        "approval_id": approval_id,
                        "thread_id": thread_id,
                        "tool_name": tool_name,
                        "tool_args": pending.tool_args,
                        "run_id": run_id,
                    },
                )

                # Wait for user decision (with timeout)
                try:
                    await asyncio.wait_for(
                        pending.decision_event.wait(),
                        timeout=300.0,  # 5 minute timeout
                    )
                except TimeoutError:
                    # Auto-reject on timeout
                    pending.approved = False
                    pending.reject_reason = "Approval timed out after 5 minutes"

                # Clean up pending approval
                self._pending_approvals.pop(thread_id, None)

                if pending.approved:
                    yield SSEEvent(
                        event="approval_result",
                        data={
                            "approval_id": approval_id,
                            "decision": "approved",
                            "tool_name": tool_name,
                        },
                    )
                    # Resume the graph — pass Command(resume=True) as input
                    agent_input = Command(resume=True)
                else:
                    yield SSEEvent(
                        event="approval_result",
                        data={
                            "approval_id": approval_id,
                            "decision": "rejected",
                            "tool_name": tool_name,
                            "reason": pending.reject_reason or "User rejected the action",
                        },
                    )
                    # Resume with rejection so the agent can handle gracefully
                    agent_input = Command(resume=False)

        except Exception as exc:
            logger.exception("Agent streaming error for thread %s", thread_id)
            yield SSEEvent(
                event="error",
                data={"error": str(exc), "thread_id": thread_id},
            )
            return

        # Emit message_end with full content
        yield SSEEvent(
            event="message_end",
            data={
                "thread_id": thread_id,
                "content": full_content,
                "tool_calls": tool_calls_data if tool_calls_data else None,
            },
        )


# Module-level singleton (initialised lazily or at app startup).
agent_service = AgentService()
