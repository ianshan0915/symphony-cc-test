"""Tests for the refactored agent streaming with native interrupt_on (SYM-83).

Covers:
- Dual stream mode (messages + updates) event mapping
- Native interrupt_on human-in-the-loop approval flow
- Approve, edit, and reject decisions
- Error handling during streaming
- Resume after approval/edit/rejection
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from app.services.agent_service import AgentService
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
            yield  # make it a generator

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
# Interrupt / approval tests (native interrupt_on)
# ---------------------------------------------------------------------------


class TestStreamResponseInterrupt:
    """Tests for the native interrupt_on human-in-the-loop flow."""

    @pytest.mark.asyncio
    async def test_interrupt_emits_approval_required(self) -> None:
        """When the graph interrupts, an approval_required event should be emitted."""
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
            for _ in range(50):
                pending = svc.get_pending_approval("t1")
                if pending is not None:
                    await svc.resolve_interrupt("t1", decision="approve")
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
        assert "allowed_decisions" in approval_evt.data

        result_evt = next(e for e in events if e.event == "approval_result")
        assert result_evt.data["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_interrupt_edit_resumes_with_modified_args(self) -> None:
        """On edit, the stream should resume with a Command containing modified args."""
        first_chunks: list[tuple[str, Any]] = [
            (
                "updates",
                {
                    "__interrupt__": [
                        {
                            "tool_name": "web_search",
                            "tool_args": {"query": "original"},
                            "run_id": "r1",
                        }
                    ]
                },
            ),
        ]
        resume_chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Searched with improved query!"), {})),
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

        async def auto_edit() -> None:
            for _ in range(50):
                pending = svc.get_pending_approval("t1")
                if pending is not None:
                    await svc.resolve_interrupt(
                        "t1",
                        decision="edit",
                        modified_args={"query": "improved"},
                    )
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(auto_edit())

        events = await _collect_events(svc, thread_id="t1", user_message="search")
        await task

        event_types = [e.event for e in events]
        assert "approval_result" in event_types

        result_evt = next(e for e in events if e.event == "approval_result")
        assert result_evt.data["decision"] == "edited"
        assert result_evt.data["modified_args"] == {"query": "improved"}

        # Verify the resume was called with Command containing HITLResponse
        from langgraph.types import Command

        assert isinstance(resume_input, Command)
        assert resume_input.resume == {
            "decisions": [
                {
                    "type": "edit",
                    "edited_action": {"name": "web_search", "args": {"query": "improved"}},
                }
            ]
        }

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
                    await svc.resolve_interrupt("t1", decision="reject", reason="Not now")
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

        # Verify the resume was called with Command containing reject HITLResponse
        from langgraph.types import Command

        assert isinstance(resume_input, Command)
        assert resume_input.resume == {"decisions": [{"type": "reject", "message": "Not now"}]}

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
                    await svc.resolve_interrupt("t1", decision="approve")
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(auto_approve())
        events = await _collect_events(svc, thread_id="t1", user_message="search kb")
        await task

        approval_evt = next(e for e in events if e.event == "approval_required")
        assert approval_evt.data["tool_name"] == "search_knowledge_base"

    @pytest.mark.asyncio
    async def test_interrupt_approval_required_includes_allowed_decisions(self) -> None:
        """The approval_required event should include allowed_decisions."""
        chunks: list[tuple[str, Any]] = [
            (
                "updates",
                {
                    "__interrupt__": [
                        {
                            "tool_name": "web_search",
                            "tool_args": {"query": "test"},
                            "run_id": "r1",
                            "allowed_decisions": ["approve", "edit", "reject"],
                        }
                    ]
                },
            ),
        ]
        resume_chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Done"), {})),
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
                    await svc.resolve_interrupt("t1", decision="approve")
                    return
                await asyncio.sleep(0.01)

        task = asyncio.create_task(auto_approve())
        events = await _collect_events(svc, thread_id="t1", user_message="search")
        await task

        approval_evt = next(e for e in events if e.event == "approval_required")
        assert approval_evt.data["allowed_decisions"] == ["approve", "edit", "reject"]


# ---------------------------------------------------------------------------
# Resume command building tests
# ---------------------------------------------------------------------------


class TestBuildResumeCommand:
    """Tests for AgentService._build_resume_command."""

    def test_approve_returns_hitl_response(self) -> None:
        from langgraph.types import Command

        cmd = AgentService._build_resume_command({"type": "approve"})
        assert isinstance(cmd, Command)
        assert cmd.resume == {"decisions": [{"type": "approve"}]}

    def test_reject_returns_hitl_response(self) -> None:
        from langgraph.types import Command

        cmd = AgentService._build_resume_command({"type": "reject", "reason": "no"})
        assert isinstance(cmd, Command)
        assert cmd.resume == {"decisions": [{"type": "reject", "message": "no"}]}

    def test_edit_returns_hitl_response_with_edited_action(self) -> None:
        from langgraph.types import Command

        cmd = AgentService._build_resume_command(
            {
                "type": "edit",
                "tool_name": "web_search",
                "modified_args": {"query": "better"},
            }
        )
        assert isinstance(cmd, Command)
        assert cmd.resume == {
            "decisions": [
                {
                    "type": "edit",
                    "edited_action": {"name": "web_search", "args": {"query": "better"}},
                }
            ]
        }

    def test_unknown_type_defaults_to_reject(self) -> None:
        from langgraph.types import Command

        cmd = AgentService._build_resume_command({"type": "unknown"})
        assert isinstance(cmd, Command)
        assert cmd.resume == {
            "decisions": [{"type": "reject", "message": "User rejected the action"}]
        }


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


# ---------------------------------------------------------------------------
# Todo update streaming tests (SYM-87)
# ---------------------------------------------------------------------------


class TestTodoUpdateStreaming:
    """Integration tests for write_todos → todo_update SSE event flow."""

    @pytest.mark.asyncio
    async def test_write_todos_emits_todo_update_event(self) -> None:
        """When the agent calls write_todos, a todo_update SSE event is emitted."""
        todos = [
            {"content": "Research API options", "status": "completed"},
            {"content": "Write implementation", "status": "in_progress"},
            {"content": "Add tests", "status": "pending"},
        ]
        tool_msg = ToolMessage(content=f"Updated todo list to {todos}", tool_call_id="call_todos_1")
        chunks: list[tuple[str, Any]] = [
            ("updates", {"tools": {"todos": todos, "messages": [tool_msg]}}),
            ("messages", (AIMessageChunk(content="Working on it"), {})),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="do a complex task")
        event_types = [e.event for e in events]

        assert "todo_update" in event_types

    @pytest.mark.asyncio
    async def test_todo_update_event_structure(self) -> None:
        """The todo_update event carries correctly structured todo items."""
        todos = [
            {"content": "Research API options", "status": "completed"},
            {"content": "Write implementation", "status": "in_progress"},
            {"content": "Add tests", "status": "pending"},
        ]
        tool_msg = ToolMessage(content=f"Updated todo list to {todos}", tool_call_id="call_todos_1")
        chunks: list[tuple[str, Any]] = [
            ("updates", {"tools": {"todos": todos, "messages": [tool_msg]}}),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="plan my work")
        todo_evt = next(e for e in events if e.event == "todo_update")

        result_todos = todo_evt.data["todos"]
        assert len(result_todos) == 3
        assert result_todos[0] == {
            "id": "1",
            "description": "Research API options",
            "status": "completed",
        }
        assert result_todos[1] == {
            "id": "2",
            "description": "Write implementation",
            "status": "in_progress",
        }
        assert result_todos[2] == {
            "id": "3",
            "description": "Add tests",
            "status": "pending",
        }

    @pytest.mark.asyncio
    async def test_todo_status_transitions_emitted_as_separate_events(self) -> None:
        """Multiple write_todos calls produce multiple todo_update events."""
        initial_todos = [
            {"content": "Step 1", "status": "in_progress"},
            {"content": "Step 2", "status": "pending"},
        ]
        updated_todos = [
            {"content": "Step 1", "status": "completed"},
            {"content": "Step 2", "status": "in_progress"},
        ]
        tool_msg_1 = ToolMessage(
            content=f"Updated todo list to {initial_todos}", tool_call_id="call_t1"
        )
        tool_msg_2 = ToolMessage(
            content=f"Updated todo list to {updated_todos}", tool_call_id="call_t2"
        )
        chunks: list[tuple[str, Any]] = [
            ("updates", {"tools": {"todos": initial_todos, "messages": [tool_msg_1]}}),
            ("messages", (AIMessageChunk(content="Doing step 1..."), {})),
            ("updates", {"tools": {"todos": updated_todos, "messages": [tool_msg_2]}}),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="multi-step task")
        todo_events = [e for e in events if e.event == "todo_update"]

        assert len(todo_events) == 2
        # First event: step 1 in_progress
        first_statuses = {t["description"]: t["status"] for t in todo_events[0].data["todos"]}
        assert first_statuses["Step 1"] == "in_progress"
        assert first_statuses["Step 2"] == "pending"
        # Second event: step 1 completed, step 2 in_progress
        second_statuses = {t["description"]: t["status"] for t in todo_events[1].data["todos"]}
        assert second_statuses["Step 1"] == "completed"
        assert second_statuses["Step 2"] == "in_progress"

    @pytest.mark.asyncio
    async def test_regular_tool_calls_do_not_produce_todo_update(self) -> None:
        """Non-write_todos tool results do not emit todo_update events."""
        tool_msg = ToolMessage(content="Search result", tool_call_id="call_1")
        chunks: list[tuple[str, Any]] = [
            ("updates", {"tools": {"messages": [tool_msg]}}),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="search for something")
        event_types = [e.event for e in events]

        assert "todo_update" not in event_types

    @pytest.mark.asyncio
    async def test_todo_update_and_tool_result_both_emitted(self) -> None:
        """write_todos produces both a tool_result (for the ToolMessage) and a todo_update."""
        todos = [{"content": "Do something", "status": "in_progress"}]
        tool_msg = ToolMessage(content=f"Updated todo list to {todos}", tool_call_id="call_todos_1")
        chunks: list[tuple[str, Any]] = [
            ("updates", {"tools": {"todos": todos, "messages": [tool_msg]}}),
        ]
        svc = AgentService(agent=_make_mock_agent(chunks))

        events = await _collect_events(svc, thread_id="t1", user_message="task")
        event_types = [e.event for e in events]

        assert "tool_result" in event_types
        assert "todo_update" in event_types
