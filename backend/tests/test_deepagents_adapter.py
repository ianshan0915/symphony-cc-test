"""Tests for the deepagents adapter event mapping (SYM-65, SYM-87)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.agents.deepagents_adapter import (
    extract_interrupt,
    map_message_chunk,
    map_state_update,
    map_todo_update,
)

# ---------------------------------------------------------------------------
# map_message_chunk tests
# ---------------------------------------------------------------------------


class TestMapMessageChunk:
    """Tests for messages-mode → SSE event mapping."""

    def test_token_content_yields_token_event(self) -> None:
        chunk = AIMessageChunk(content="Hello")
        events = map_message_chunk(chunk, {})
        assert len(events) == 1
        assert events[0].event == "token"
        assert events[0].data["token"] == "Hello"

    def test_empty_content_yields_no_events(self) -> None:
        chunk = AIMessageChunk(content="")
        events = map_message_chunk(chunk, {})
        assert events == []

    def test_non_ai_chunk_yields_no_events(self) -> None:
        events = map_message_chunk("not a chunk", {})
        assert events == []

    def test_tool_call_chunk_yields_tool_call_event(self) -> None:
        chunk = AIMessageChunk(
            content="",
            tool_call_chunks=[
                {"name": "web_search", "args": '{"query": "test"}', "id": "call_1", "index": 0}
            ],
        )
        events = map_message_chunk(chunk, {})
        assert len(events) == 1
        assert events[0].event == "tool_call"
        assert events[0].data["tool_name"] == "web_search"
        assert events[0].data["run_id"] == "call_1"

    def test_tool_call_chunk_without_name_is_skipped(self) -> None:
        """Continuation chunks (no name) should not emit events."""
        chunk = AIMessageChunk(
            content="",
            tool_call_chunks=[
                {"name": None, "args": '{"query": "more"}', "id": "call_1", "index": 0}
            ],
        )
        events = map_message_chunk(chunk, {})
        assert events == []

    def test_token_and_tool_call_together(self) -> None:
        chunk = AIMessageChunk(
            content="Thinking...",
            tool_call_chunks=[{"name": "calculator", "args": "{}", "id": "call_2", "index": 0}],
        )
        events = map_message_chunk(chunk, {})
        assert len(events) == 2
        assert events[0].event == "token"
        assert events[1].event == "tool_call"


# ---------------------------------------------------------------------------
# map_state_update tests
# ---------------------------------------------------------------------------


class TestMapStateUpdate:
    """Tests for updates-mode → SSE event mapping."""

    def test_tool_message_yields_tool_result_event(self) -> None:
        tool_msg = ToolMessage(content="Result data", tool_call_id="call_1")
        update: dict[str, Any] = {"tools": {"messages": [tool_msg]}}
        events = map_state_update(update)
        assert len(events) == 1
        assert events[0].event == "tool_result"
        assert events[0].data["run_id"] == "call_1"
        assert events[0].data["output"] == "Result data"

    def test_interrupt_key_is_skipped(self) -> None:
        update: dict[str, Any] = {"__interrupt__": [{"value": {"tool_name": "search"}}]}
        events = map_state_update(update)
        assert events == []

    def test_non_tool_messages_are_ignored(self) -> None:
        update: dict[str, Any] = {"agent": {"messages": [AIMessageChunk(content="Hi")]}}
        events = map_state_update(update)
        assert events == []

    def test_list_format_node_output(self) -> None:
        tool_msg = ToolMessage(content="OK", tool_call_id="call_2")
        update: dict[str, Any] = {"tools": [tool_msg]}
        events = map_state_update(update)
        assert len(events) == 1
        assert events[0].data["run_id"] == "call_2"

    def test_long_output_is_not_truncated(self) -> None:
        """With CompositeBackend offloading, large outputs are passed through."""
        long_content = "x" * 3000
        tool_msg = ToolMessage(content=long_content, tool_call_id="call_3")
        update: dict[str, Any] = {"tools": {"messages": [tool_msg]}}
        events = map_state_update(update)
        assert len(events[0].data["output"]) == 3000

    def test_filesystem_tool_emits_file_event(self) -> None:
        """Native filesystem tools produce both file_event and tool_result."""
        tool_msg = ToolMessage(
            content="file contents here", tool_call_id="call_4", name="read_file"
        )
        update: dict[str, Any] = {"tools": {"messages": [tool_msg]}}
        events = map_state_update(update)
        assert len(events) == 2
        assert events[0].event == "file_event"
        assert events[0].data["tool_name"] == "read_file"
        assert events[0].data["output"] == "file contents here"
        assert events[1].event == "tool_result"
        assert events[1].data["run_id"] == "call_4"

    def test_non_filesystem_tool_no_file_event(self) -> None:
        """Non-filesystem tools should only produce tool_result (no file_event)."""
        tool_msg = ToolMessage(content="search results", tool_call_id="call_5", name="web_search")
        update: dict[str, Any] = {"tools": {"messages": [tool_msg]}}
        events = map_state_update(update)
        assert len(events) == 1
        assert events[0].event == "tool_result"


# ---------------------------------------------------------------------------
# extract_interrupt tests
# ---------------------------------------------------------------------------


class TestExtractInterrupt:
    """Tests for interrupt detection from updates-mode payloads."""

    def test_no_interrupt_returns_none(self) -> None:
        update: dict[str, Any] = {"agent": {"messages": []}}
        assert extract_interrupt(update) is None

    def test_empty_interrupt_returns_none(self) -> None:
        update: dict[str, Any] = {"__interrupt__": []}
        assert extract_interrupt(update) is None

    def test_dict_interrupt_value(self) -> None:
        update: dict[str, Any] = {
            "__interrupt__": [{"tool_name": "web_search", "tool_args": {"q": "test"}}]
        }
        result = extract_interrupt(update)
        assert result is not None
        assert result["tool_name"] == "web_search"

    def test_interrupt_object_with_value_attribute(self) -> None:
        """LangGraph Interrupt objects have a .value attribute."""
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"tool_name": "search", "tool_args": {}}
        update: dict[str, Any] = {"__interrupt__": [interrupt_obj]}
        result = extract_interrupt(update)
        assert result is not None
        assert result["tool_name"] == "search"

    def test_non_dict_value_wrapped_in_data(self) -> None:
        interrupt_obj = MagicMock()
        interrupt_obj.value = "raw_string"
        update: dict[str, Any] = {"__interrupt__": [interrupt_obj]}
        result = extract_interrupt(update)
        assert result == {"data": "raw_string"}

    def test_plain_non_dict_interrupt(self) -> None:
        """Non-dict, non-object interrupt entries are wrapped."""
        update: dict[str, Any] = {"__interrupt__": [42]}
        result = extract_interrupt(update)
        assert result == {"data": 42}


# ---------------------------------------------------------------------------
# map_todo_update tests
# ---------------------------------------------------------------------------


class TestMapTodoUpdate:
    """Tests for write_todos detection and todo_update SSE event mapping (SYM-87)."""

    def test_todos_in_state_update_yields_todo_update_event(self) -> None:
        """A state update containing a ``todos`` key emits a todo_update event."""
        todos = [
            {"content": "Research API options", "status": "completed"},
            {"content": "Write implementation", "status": "in_progress"},
            {"content": "Add tests", "status": "pending"},
        ]
        update: dict[str, Any] = {"tools": {"todos": todos, "messages": []}}
        events = map_todo_update(update)
        assert len(events) == 1
        assert events[0].event == "todo_update"

    def test_todo_update_event_contains_structured_list(self) -> None:
        """The todo_update data contains a structured todos list with id, description, status."""
        todos = [
            {"content": "Research API options", "status": "completed"},
            {"content": "Write implementation", "status": "in_progress"},
            {"content": "Add tests", "status": "pending"},
        ]
        update: dict[str, Any] = {"tools": {"todos": todos, "messages": []}}
        events = map_todo_update(update)
        assert len(events) == 1
        result_todos = events[0].data["todos"]
        assert len(result_todos) == 3

        assert result_todos[0] == {"id": "1", "description": "Research API options", "status": "completed"}
        assert result_todos[1] == {"id": "2", "description": "Write implementation", "status": "in_progress"}
        assert result_todos[2] == {"id": "3", "description": "Add tests", "status": "pending"}

    def test_todo_ids_are_one_based_strings(self) -> None:
        """IDs are assigned as 1-based string indices."""
        todos = [
            {"content": "Task A", "status": "pending"},
            {"content": "Task B", "status": "pending"},
        ]
        update: dict[str, Any] = {"tools": {"todos": todos}}
        events = map_todo_update(update)
        ids = [t["id"] for t in events[0].data["todos"]]
        assert ids == ["1", "2"]

    def test_empty_todos_list_yields_todo_update_event(self) -> None:
        """An empty todos list still emits a todo_update (clears the list)."""
        update: dict[str, Any] = {"tools": {"todos": []}}
        events = map_todo_update(update)
        assert len(events) == 1
        assert events[0].event == "todo_update"
        assert events[0].data["todos"] == []

    def test_status_transitions_are_surfaced(self) -> None:
        """All three status values (pending, in_progress, completed) are preserved."""
        todos = [
            {"content": "Step 1", "status": "completed"},
            {"content": "Step 2", "status": "in_progress"},
            {"content": "Step 3", "status": "pending"},
        ]
        update: dict[str, Any] = {"tools": {"todos": todos}}
        events = map_todo_update(update)
        statuses = [t["status"] for t in events[0].data["todos"]]
        assert statuses == ["completed", "in_progress", "pending"]

    def test_update_without_todos_key_yields_no_events(self) -> None:
        """State updates with no ``todos`` key produce no todo_update events."""
        tool_msg = ToolMessage(content="Search result", tool_call_id="call_1")
        update: dict[str, Any] = {"tools": {"messages": [tool_msg]}}
        events = map_todo_update(update)
        assert events == []

    def test_interrupt_key_is_skipped(self) -> None:
        """The __interrupt__ key is ignored by map_todo_update."""
        update: dict[str, Any] = {
            "__interrupt__": [{"tool_name": "web_search"}],
        }
        events = map_todo_update(update)
        assert events == []

    def test_non_dict_node_output_is_skipped(self) -> None:
        """List-format node outputs (no dict to check for todos) produce no events."""
        tool_msg = ToolMessage(content="OK", tool_call_id="call_2")
        update: dict[str, Any] = {"tools": [tool_msg]}
        events = map_todo_update(update)
        assert events == []

    def test_empty_update_yields_no_events(self) -> None:
        """An entirely empty update dict produces no events."""
        events = map_todo_update({})
        assert events == []

    def test_todo_content_mapped_to_description(self) -> None:
        """The ``content`` field from the Todo TypedDict is exposed as ``description``."""
        todos = [{"content": "Deploy to production", "status": "pending"}]
        update: dict[str, Any] = {"tools": {"todos": todos}}
        events = map_todo_update(update)
        assert events[0].data["todos"][0]["description"] == "Deploy to production"
        assert "content" not in events[0].data["todos"][0]

    def test_missing_status_defaults_to_pending(self) -> None:
        """Todos missing the status field default to ``pending``."""
        todos = [{"content": "Task without status"}]
        update: dict[str, Any] = {"tools": {"todos": todos}}
        events = map_todo_update(update)
        assert events[0].data["todos"][0]["status"] == "pending"

    def test_write_todos_tool_message_in_same_update_also_produces_tool_result(self) -> None:
        """When write_todos fires, map_state_update still emits tool_result for the ToolMessage."""
        todos = [{"content": "Do something", "status": "in_progress"}]
        tool_msg = ToolMessage(
            content=f"Updated todo list to {todos}", tool_call_id="call_todos_1"
        )
        update: dict[str, Any] = {"tools": {"todos": todos, "messages": [tool_msg]}}

        # map_todo_update emits todo_update
        todo_events = map_todo_update(update)
        assert len(todo_events) == 1
        assert todo_events[0].event == "todo_update"

        # map_state_update still emits tool_result for the ToolMessage
        state_events = map_state_update(update)
        assert len(state_events) == 1
        assert state_events[0].event == "tool_result"
        assert state_events[0].data["run_id"] == "call_todos_1"
