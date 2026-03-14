"""Agent service — manages agent lifecycle, thread state, and streaming."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.agents.factory import create_deep_agent
from app.models.thread import Thread

logger = logging.getLogger(__name__)


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
# Agent service
# ---------------------------------------------------------------------------


class AgentService:
    """Manages agent creation, invocation, and SSE event streaming.

    Holds a singleton agent graph (compiled once at startup) and provides
    a streaming interface that yields SSE events for each step of the agent
    execution.
    """

    def __init__(self, agent: CompiledStateGraph | None = None) -> None:
        self._agent = agent

    @property
    def agent(self) -> CompiledStateGraph:
        """Return the agent graph, creating one lazily if needed."""
        if self._agent is None:
            self._agent = create_deep_agent()
        return self._agent

    def set_agent(self, agent: CompiledStateGraph) -> None:
        """Replace the current agent graph (useful for testing)."""
        self._agent = agent

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
        4. ``message_end`` — signals the end of the assistant turn with the
           full message content.

        On error an ``error`` event is yielded and the stream terminates.
        """
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}  # type: ignore[assignment]

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
                config=config,  # type: ignore[arg-type]
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

                # Tool invocations
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
