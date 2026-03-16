"""Agent service — manages agent lifecycle, thread state, and streaming.

Uses deepagents' ``astream()`` API with dual stream modes (``messages`` +
``updates``) and its native ``interrupt_on`` parameter for human-in-the-loop
approval flows.

The ``interrupt_on`` configuration passed to ``create_deep_agent()`` tells
deepagents which tools should pause for user approval.  When an interrupt
fires the stream emits an ``approval_required`` SSE event and waits for the
caller to resolve the decision.  Supported decisions are:

* **approve** — resume execution of the tool as-is.
* **edit** — modify the tool arguments and then execute.
* **reject** — skip the tool and let the agent handle gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
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
from app.agents.factory import UserContext, create_deep_agent
from app.models.thread import Thread
from app.services.sse import SSEEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration — native interrupt_on for human-in-the-loop approval
# ---------------------------------------------------------------------------

INTERRUPT_ON: dict[str, Any] = {
    "web_search": {"allowed_decisions": ["approve", "edit", "reject"]},
    "search_knowledge_base": True,
    # Add tool names here that should pause for user approval.
    # Use ``True`` for default approve/reject, or a dict with
    # ``{"allowed_decisions": [...]}`` for richer control.
}

# Backward-compatible alias for code that references the old constant.
TOOLS_REQUIRING_APPROVAL: set[str] = set(INTERRUPT_ON)

# Maps decision type → past-tense label used in approval_result SSE events.
_DECISION_PAST_TENSE: dict[str, str] = {
    "approve": "approved",
    "edit": "edited",
    "reject": "rejected",
}


# ---------------------------------------------------------------------------
# Pending interrupt state (lightweight replacement for PendingApproval)
# ---------------------------------------------------------------------------


class _PendingInterrupt:
    """Lightweight container for an in-flight interrupt awaiting a decision.

    This is an internal detail of :class:`AgentService` — external code
    interacts via :meth:`AgentService.resolve_interrupt`.
    """

    __slots__ = ("approval_id", "decision", "decision_event", "interrupt_data", "thread_id")

    def __init__(self, thread_id: str, approval_id: str, interrupt_data: dict[str, Any]) -> None:
        self.thread_id = thread_id
        self.approval_id = approval_id
        self.interrupt_data = interrupt_data
        self.decision_event = asyncio.Event()
        # Set by resolve_interrupt before signalling the event.
        self.decision: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Agent service
# ---------------------------------------------------------------------------


class AgentService:
    """Manages agent creation, invocation, and SSE event streaming.

    Holds a singleton agent graph (compiled once at startup) and provides
    a streaming interface that yields SSE events for each step of the agent
    execution.  Supports human-in-the-loop approval via deepagents' native
    ``interrupt_on`` parameter.
    """

    def __init__(self, agent: CompiledStateGraph | None = None) -> None:  # type: ignore[type-arg]
        self._agent = agent
        # Map of thread_id -> _PendingInterrupt for active interrupt requests
        self._pending_interrupts: dict[str, _PendingInterrupt] = {}

    @property
    def agent(self) -> CompiledStateGraph:  # type: ignore[type-arg]
        """Return the default agent graph, creating one lazily if needed."""
        if self._agent is None:
            self._agent = create_deep_agent(interrupt_on=INTERRUPT_ON)
        return self._agent

    def get_agent(self, assistant_type: str | None = None) -> CompiledStateGraph:  # type: ignore[type-arg]
        """Return an agent for the given assistant type.

        If *assistant_type* is ``None`` or ``"general"``, returns the default
        singleton agent. Specialized types create a new agent with the
        appropriate prompt and tool configuration.
        """
        if not assistant_type or assistant_type == "general":
            return self.agent
        return create_deep_agent(assistant_type=assistant_type, interrupt_on=INTERRUPT_ON)

    def set_agent(self, agent: CompiledStateGraph) -> None:  # type: ignore[type-arg]
        """Replace the current agent graph (useful for testing)."""
        self._agent = agent

    # ------------------------------------------------------------------
    # Interrupt management (replaces old PendingApproval / resolve_approval)
    # ------------------------------------------------------------------

    def get_pending_approval(self, thread_id: str) -> _PendingInterrupt | None:
        """Return the pending interrupt for a thread, if any.

        Kept as ``get_pending_approval`` for backward compatibility with the
        ``GET /chat/approval/{thread_id}`` endpoint.
        """
        return self._pending_interrupts.get(thread_id)

    async def resolve_interrupt(
        self,
        thread_id: str,
        *,
        decision: str,
        reason: str | None = None,
        modified_args: dict[str, Any] | None = None,
    ) -> bool:
        """Resolve a pending interrupt for the given thread.

        Parameters
        ----------
        thread_id:
            Thread whose interrupt should be resolved.
        decision:
            One of ``"approve"``, ``"edit"``, or ``"reject"``.
        reason:
            Optional reason (used with ``"reject"``).
        modified_args:
            Modified tool arguments (used with ``"edit"``).

        Returns ``True`` if an interrupt was found and resolved, ``False`` otherwise.
        """
        pending = self._pending_interrupts.get(thread_id)
        if pending is None:
            return False

        pending.decision = {
            "type": decision,
            "reason": reason,
            "modified_args": modified_args,
        }
        pending.decision_event.set()
        return True

    async def resolve_approval(
        self,
        thread_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> bool:
        """Backward-compatible wrapper around :meth:`resolve_interrupt`.

        Translates the old ``approved: bool`` interface to the new
        decision-based interface.
        """
        decision = "approve" if approved else "reject"
        return await self.resolve_interrupt(thread_id, decision=decision, reason=reason)

    # ------------------------------------------------------------------
    # Streaming helpers
    # ------------------------------------------------------------------

    async def _stream_agent(
        self,
        active_agent: CompiledStateGraph,  # type: ignore[type-arg]
        agent_input: Any,
        config: dict[str, Any],
        context: UserContext | None = None,
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

        Parameters
        ----------
        context:
            Optional ``UserContext`` passed through to ``astream()`` so
            deepagents' ``StoreBackend`` can resolve the per-user namespace
            ``("filesystem", user_id)`` for AGENTS.md reads and writes.
        """
        async for event in active_agent.astream(
            agent_input,
            config=config,  # type: ignore[call-overload]
            context=context,
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
    # Resume command helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_resume_command(decision: dict[str, Any]) -> Command:
        """Build a :class:`Command` to resume the graph after an interrupt.

        Maps the three decision types to the appropriate resume value:

        * ``approve`` → ``Command(resume=True)``
        * ``edit``    → ``Command(resume={"decision": "edit", "tool_args": ...})``
        * ``reject``  → ``Command(resume=False)``
        """
        dtype = decision.get("type", "reject")
        if dtype == "approve":
            return Command(resume=True)
        if dtype == "edit":
            return Command(
                resume={
                    "decision": "edit",
                    "tool_args": decision.get("modified_args") or {},
                }
            )
        # reject (default)
        return Command(resume=False)

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
        user_id: str | None = None,
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
        user_id:
            Authenticated user identifier.  When provided, a
            ``UserContext(user_id=user_id)`` is passed to the agent so
            ``StoreBackend`` resolves memory reads/writes to the user's own
            namespace ``("filesystem", user_id)`` — matching exactly the
            namespace written by ``PUT /memory``.

        Yields events in order:
        1. ``message_start`` — signals the beginning of an assistant turn.
        2. ``token`` — each incremental text token from the LLM.
        3. ``tool_call`` — when the agent invokes a tool.
        4. ``approval_required`` — when a native interrupt requests human
           approval (includes ``allowed_decisions``).
        5. ``approval_result`` — after the user approves/edits/rejects.
        6. ``tool_result`` — tool execution result.
        7. ``message_end`` — signals the end of the assistant turn with the
           full message content.

        Note: a ``memory_updated`` SSE event is emitted by the HTTP layer
        (``chat.py``) *after* ``message_end`` when the agent has written new
        content to the user's AGENTS.md during this turn.

        On error an ``error`` event is yielded and the stream terminates.
        """
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        agent_input: Any = {"messages": [HumanMessage(content=user_message)]}

        # Build per-user runtime context so StoreBackend resolves the correct
        # user-scoped namespace ("filesystem", user_id) for AGENTS.md reads.
        agent_context: UserContext | None = UserContext(user_id=user_id) if user_id else None

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

                async for mode, chunk, ns in self._stream_agent(
                    active_agent, agent_input, config, agent_context
                ):
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

                # --- Handle native interrupt ---
                tool_name = interrupt_data.get("tool_name", "unknown")
                tool_args = interrupt_data.get("tool_args", {})
                run_id = interrupt_data.get("run_id", "")
                allowed_decisions = interrupt_data.get(
                    "allowed_decisions",
                    _allowed_decisions_for_tool(tool_name),
                )
                approval_id = str(uuid.uuid4())

                pending = _PendingInterrupt(
                    thread_id=thread_id,
                    approval_id=approval_id,
                    interrupt_data=interrupt_data,
                )
                self._pending_interrupts[thread_id] = pending
                try:
                    # Emit approval_required event (backward compatible + new fields)
                    yield SSEEvent(
                        event="approval_required",
                        data={
                            "approval_id": approval_id,
                            "thread_id": thread_id,
                            "tool_name": tool_name,
                            "tool_args": (
                                tool_args if isinstance(tool_args, dict) else {"input": tool_args}
                            ),
                            "run_id": run_id,
                            "allowed_decisions": allowed_decisions,
                        },
                    )

                    # Wait for user decision (with timeout)
                    try:
                        await asyncio.wait_for(
                            pending.decision_event.wait(),
                            timeout=300.0,  # 5 minute timeout
                        )
                    except TimeoutError:
                        pending.decision = {
                            "type": "reject",
                            "reason": "Approval timed out after 5 minutes",
                        }
                finally:
                    # Always clean up, even if the stream is cancelled mid-wait
                    self._pending_interrupts.pop(thread_id, None)

                decision = pending.decision or {"type": "reject", "reason": "No decision received"}
                dtype = decision.get("type", "reject")

                # Build approval_result event data based on decision type
                result_data: dict[str, Any] = {
                    "approval_id": approval_id,
                    "decision": _DECISION_PAST_TENSE.get(dtype, dtype),
                    "tool_name": tool_name,
                }
                if dtype == "edit":
                    result_data["modified_args"] = decision.get("modified_args", {})
                elif dtype == "reject":
                    result_data["reason"] = decision.get("reason") or "User rejected the action"
                yield SSEEvent(event="approval_result", data=result_data)

                # Resume the graph with the appropriate command
                agent_input = self._build_resume_command(decision)

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


def _allowed_decisions_for_tool(tool_name: str) -> list[str]:
    """Return the allowed decisions for a tool based on ``INTERRUPT_ON`` config."""
    cfg = INTERRUPT_ON.get(tool_name)
    if isinstance(cfg, dict):
        return cfg.get("allowed_decisions", ["approve", "reject"])
    # Default for ``True`` or unknown tools
    return ["approve", "reject"]


# Module-level singleton (initialised lazily or at app startup).
agent_service = AgentService()
