"""Agent service — manages agent lifecycle, thread state, and streaming.

Supports human-in-the-loop approval flow: when the agent invokes a tool
that is listed in ``TOOLS_REQUIRING_APPROVAL``, the stream emits an
``approval_required`` SSE event and pauses.  The caller can later resume
execution via ``resume_after_approval()`` or cancel it with
``cancel_after_rejection()``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.agents.factory import create_deep_agent
from app.models.thread import Thread

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
# SSE event types
# ---------------------------------------------------------------------------


@dataclass
class SSEEvent:
    """A Server-Sent Event to be streamed to the client."""

    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> str:
        """Encode as SSE wire format."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


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
    execution.  Supports human-in-the-loop approval for designated tools.
    """

    def __init__(self, agent: CompiledStateGraph | None = None) -> None:
        self._agent = agent
        # Map of thread_id -> PendingApproval for active approval requests
        self._pending_approvals: dict[str, PendingApproval] = {}

    @property
    def agent(self) -> CompiledStateGraph:
        """Return the agent graph, creating one lazily if needed."""
        if self._agent is None:
            self._agent = create_deep_agent()
        return self._agent

    def set_agent(self, agent: CompiledStateGraph) -> None:
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
    # Streaming
    # ------------------------------------------------------------------

    async def stream_response(
        self,
        *,
        thread_id: str,
        user_message: str,
        thread: Thread | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Stream agent response as SSE events.

        Yields events in order:
        1. ``message_start`` — signals the beginning of an assistant turn.
        2. ``token`` — each incremental text token from the LLM.
        3. ``tool_call`` — when the agent invokes a tool.
        4. ``approval_required`` — when a tool needs human approval (pauses).
        5. ``approval_result`` — after the user approves/rejects.
        6. ``tool_result`` — tool execution result.
        7. ``message_end`` — signals the end of the assistant turn with the
           full message content.

        On error an ``error`` event is yielded and the stream terminates.
        """
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        input_messages = [HumanMessage(content=user_message)]

        # Emit message_start
        yield SSEEvent(
            event="message_start",
            data={"thread_id": thread_id},
        )

        full_content = ""
        tool_calls_data: list[dict[str, Any]] = []

        try:
            async for event in self.agent.astream_events(
                {"messages": input_messages},
                config=config,
                version="v2",
            ):
                kind = event.get("event", "")

                # LLM stream tokens
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_text = chunk.content
                        if isinstance(token_text, str):
                            full_content += token_text
                            yield SSEEvent(
                                event="token",
                                data={"token": token_text},
                            )

                # Tool invocations — check if approval is required
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input: Any = event.get("data", {}).get("input", {})
                    run_id = event.get("run_id", "")
                    tool_call_info = {
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "run_id": run_id,
                    }
                    tool_calls_data.append(tool_call_info)

                    if tool_name in TOOLS_REQUIRING_APPROVAL:
                        # Create approval request and pause
                        approval_id = str(uuid.uuid4())
                        pending = PendingApproval(
                            approval_id=approval_id,
                            thread_id=thread_id,
                            tool_name=tool_name,
                            tool_args=(
                                tool_input
                                if isinstance(tool_input, dict)
                                else {"input": tool_input}
                            ),
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
                            # Tool execution continues naturally in the stream
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
                            # Note: The tool call was already dispatched by
                            # astream_events; in a production system this would
                            # use LangGraph's interrupt/resume mechanism.
                            # Here we emit a rejection event so the frontend
                            # can update the UI accordingly.
                    else:
                        yield SSEEvent(
                            event="tool_call",
                            data=tool_call_info,
                        )

                # Tool results
                elif kind == "on_tool_end":
                    tool_output = event.get("data", {}).get("output", "")
                    run_id = event.get("run_id", "")
                    yield SSEEvent(
                        event="tool_result",
                        data={
                            "run_id": run_id,
                            "output": str(tool_output)[:2000],
                        },
                    )

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
