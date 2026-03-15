"""Tests for the refactored agent streaming with deepagents astream() (SYM-65).

Covers:
- Dual stream mode (messages + updates) event mapping
- Interrupt-based human-in-the-loop approval flow
- Error handling during streaming
- Resume after approval/rejection
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from app.services.agent_service import AgentService, PendingApproval
from app.services.sse import SSEEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_agent(stream_chunks: list[tuple[str, Any]]) -> MagicMock:
    """Create a mock agent whose ``astream()`` yields the given (mode, chunk) pairs."""
    mock_agent = MagicMock()

    async def fake_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        for chunk in stream_chunks:
            yield chunk

    mock_agent.astream = fake_astream
    return mock_agent


async def _collect_events(svc: AgentService, **kwargs: Any) -> list[SSEEvent]:
    """Collect all SSE events from stream_response."""
    events: list[SSEEvent] = []
    async for evt in svc.stream_response(**kwargs):
        events.append(evt)
    return events


# ---------------------------------------------------------------------------
# Basic streaming tests
# ---------------------------------------------------------------------------


class TestStreamResponseBasic:
    """Tests for the basic (non-interrupt) streaming path."""

    @pytest.mark.asyncio
    async def test_token_streaming(self) -> None:
        """Tokens from messages mode should appear as SSE token events."""
        chunks = [
            ("messages", (AIMessageChunk(content="Hello"), {"langgraph_node": "agent"})),
            ("messages", (AIMessageChunk(content=" world"), {"langgraph_node": "agent"})),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="hi")
        event_types = [e.event for e in events]

        assert event_types[0] == "message_start"
        assert event_types[1] == "token"
        assert event_types[2] == "token"
        assert event_types[-1] == "message_end"

        # Verify full content in message_end
        end_evt = events[-1]
        assert end_evt.data["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_tool_call_and_result(self) -> None:
        """Tool calls and results should be mapped correctly."""
        tool_msg = ToolMessage(content="Search result", tool_call_id="call_1")
        chunks: list[tuple[str, Any]] = [
            (
                "messages",
                (
                    AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {"name": "web_search", "args": "{}", "id": "call_1", "index": 0}
                        ],
                    ),
                    {},
                ),
            ),
            ("updates", {"tools": {"messages": [tool_msg]}}),
            ("messages", (AIMessageChunk(content="Found it!"), {})),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="search for X")
        event_types = [e.event for e in events]

        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "token" in event_types

        tool_call_evt = next(e for e in events if e.event == "tool_call")
        assert tool_call_evt.data["tool_name"] == "web_search"

        tool_result_evt = next(e for e in events if e.event == "tool_result")
        assert tool_result_evt.data["output"] == "Search result"

    @pytest.mark.asyncio
    async def test_empty_stream(self) -> None:
        """An empty agent stream should still emit message_start and message_end."""
        svc = AgentService(agent=_make_mock_agent([]))

        events = await _collect_events(svc, thread_id="t1", user_message="hi")
        event_types = [e.event for e in events]

        assert event_types == ["message_start", "message_end"]

    @pytest.mark.asyncio
    async def test_error_during_streaming(self) -> None:
        """An exception during streaming should emit an error event."""
        mock_agent = MagicMock()

        async def failing_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            raise RuntimeError("LLM unavailable")
            yield  # make it a generator  # noqa: RUF028

        mock_agent.astream = failing_astream
        svc = AgentService(agent=mock_agent)

        events = await _collect_events(svc, thread_id="t1", user_message="hi")
        event_types = [e.event for e in events]

        assert "message_start" in event_types
        assert "error" in event_types
        assert "message_end" not in event_types

        error_evt = next(e for e in events if e.event == "error")
        assert "LLM unavailable" in error_evt.data["error"]


# ---------------------------------------------------------------------------
# Interrupt / approval tests
# ---------------------------------------------------------------------------


class TestStreamResponseInterrupt:
    """Tests for the interrupt-based human-in-the-loop flow."""

    @pytest.mark.asyncio
    async def test_interrupt_emits_approval_required(self) -> None:
        """When the graph interrupts, an approval_required event should be emitted."""
        # First stream ends with interrupt, second stream (resume) completes
        first_chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Let me search"), {})),
            (
                "updates",
                {
                    "__interrupt__": [
                        {
                            "tool_name": "web_search",
                            "tool_args": {"query": "test"},
                            "run_id": "r1",
                        }
                    ]
                },
            ),
        ]
        resume_chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Done!"), {})),
        ]

        call_count = 0

        mock_agent = MagicMock()

        async def multi_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            nonlocal call_count
            chunks = first_chunks if call_count == 0 else resume_chunks
            call_count += 1
            for chunk in chunks:
                yield chunk

        mock_agent.astream = multi_astream
        svc = AgentService(agent=mock_agent)

        # Auto-approve in a background task
        async def auto_approve() -> None:
            # Wait until the pending approval appears
            for _ in range(50):
                pending = svc.get_pending_approval("t1")
                if pending is not None:
                    await svc.resolve_approval("t1", approved=True)
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(auto_approve())

        events = await _collect_events(svc, thread_id="t1", user_message="search something")
        await task

        event_types = [e.event for e in events]

        assert "approval_required" in event_types
        assert "approval_result" in event_types
        assert "message_end" in event_types

        approval_evt = next(e for e in events if e.event == "approval_required")
        assert approval_evt.data["tool_name"] == "web_search"

        result_evt = next(e for e in events if e.event == "approval_result")
        assert result_evt.data["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_interrupt_rejection_resumes_with_false(self) -> None:
        """On rejection, the stream should resume with Command(resume=False)."""
        first_chunks: list[tuple[str, Any]] = [
            (
                "updates",
                {
                    "__interrupt__": [
                        {
                            "tool_name": "web_search",
                            "tool_args": {},
                            "run_id": "r1",
                        }
                    ]
                },
            ),
        ]
        resume_chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="OK, I won't search."), {})),
        ]

        call_count = 0
        resume_input = None
        mock_agent = MagicMock()

        async def multi_astream(input: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            nonlocal call_count, resume_input
            chunks = first_chunks if call_count == 0 else resume_chunks
            if call_count > 0:
                resume_input = input
            call_count += 1
            for chunk in chunks:
                yield chunk

        mock_agent.astream = multi_astream
        svc = AgentService(agent=mock_agent)

        async def auto_reject() -> None:
            for _ in range(50):
                pending = svc.get_pending_approval("t1")
                if pending is not None:
                    await svc.resolve_approval("t1", approved=False, reason="Not now")
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(auto_reject())

        events = await _collect_events(svc, thread_id="t1", user_message="search")
        await task

        event_types = [e.event for e in events]
        assert "approval_result" in event_types

        result_evt = next(e for e in events if e.event == "approval_result")
        assert result_evt.data["decision"] == "rejected"
        assert result_evt.data["reason"] == "Not now"

        # Verify the resume was called with Command(resume=False)
        from langgraph.types import Command

        assert isinstance(resume_input, Command)
        assert resume_input.resume is False

    @pytest.mark.asyncio
    async def test_interrupt_with_langgraph_interrupt_object(self) -> None:
        """The interrupt handler should work with LangGraph Interrupt objects."""
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"tool_name": "search_knowledge_base", "tool_args": {"q": "arch"}}

        chunks: list[tuple[str, Any]] = [
            ("updates", {"__interrupt__": [interrupt_obj]}),
        ]
        resume_chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Found info"), {})),
        ]

        call_count = 0
        mock_agent = MagicMock()

        async def multi_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            nonlocal call_count
            chunks_to_yield = chunks if call_count == 0 else resume_chunks
            call_count += 1
            for c in chunks_to_yield:
                yield c

        mock_agent.astream = multi_astream
        svc = AgentService(agent=mock_agent)

        async def auto_approve() -> None:
            for _ in range(50):
                if svc.get_pending_approval("t1"):
                    await svc.resolve_approval("t1", approved=True)
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(auto_approve())
        events = await _collect_events(svc, thread_id="t1", user_message="search kb")
        await task

        approval_evt = next(e for e in events if e.event == "approval_required")
        assert approval_evt.data["tool_name"] == "search_knowledge_base"


# ---------------------------------------------------------------------------
# SSEEvent shared module tests
# ---------------------------------------------------------------------------


class TestSSEEventShared:
    """Tests that SSEEvent from sse.py works correctly everywhere."""

    def test_sse_event_encode(self) -> None:
        evt = SSEEvent(event="token", data={"token": "hi"})
        encoded = evt.encode()
        assert "event: token" in encoded
        assert '"token": "hi"' in encoded
        assert encoded.endswith("\n\n")

    def test_sse_event_backward_compat_import(self) -> None:
        """SSEEvent should be importable from agent_service for backward compatibility."""
        from app.services.agent_service import SSEEvent as AgentSSE

        assert AgentSSE is SSEEvent
