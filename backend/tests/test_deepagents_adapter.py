"""Tests for the deepagents adapter event mapping (SYM-65)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.agents.deepagents_adapter import (
    extract_interrupt,
    map_message_chunk,
    map_state_update,
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

    def test_long_output_is_truncated(self) -> None:
        long_content = "x" * 3000
        tool_msg = ToolMessage(content=long_content, tool_call_id="call_3")
        update: dict[str, Any] = {"tools": {"messages": [tool_msg]}}
        events = map_state_update(update)
        assert len(events[0].data["output"]) == 2000


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
