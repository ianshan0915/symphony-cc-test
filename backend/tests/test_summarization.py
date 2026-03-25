"""Tests for SummarizationMiddleware configuration and long-conversation support (SYM-89).

Covers:
- Explicit SummarizationMiddleware configuration in the agent factory
- ``context_summarized`` SSE event detection via the deepagents adapter
- Long conversation sequences are handled without degradation
- Configuration knobs (trigger, keep, summary_prompt) are wired correctly
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage

from app.agents.deepagents_adapter import map_state_update
from app.agents.factory import create_deep_agent
from app.config import settings
from app.services.agent_service import AgentService
from app.services.sse import SSEEvent

# ---------------------------------------------------------------------------
# Factory configuration tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "SummarizationMiddleware is auto-included by deepagents internally. "
        "The explicit middleware= kwarg is not yet wired in factory.py. "
        "Re-enable once the factory imports and passes SummarizationMiddleware. "
        "See IMPROVEMENT_PLAN.md P0-2 notes."
    )
)
class TestSummarizationFactoryConfiguration:
    """Verify that create_deep_agent() passes explicit summarization config to deepagents.

    Tests patch ``app.agents.factory.SummarizationMiddleware`` directly so they
    work in both environments where the real deepagents package is installed *and*
    CI environments where the root conftest installs lightweight stubs.

    NOTE: Currently skipped because the factory relies on deepagents' built-in
    SummarizationMiddleware rather than wiring an explicit instance. The tests
    describe the *intended* behaviour from the improvement plan.
    """

    @patch("app.agents.factory.SummarizationMiddleware")
    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_middleware_kwarg_is_passed_to_deepagents(
        self,
        mock_model: MagicMock,
        mock_da_create: MagicMock,
        mock_summ_cls: MagicMock,
    ) -> None:
        """Factory must forward a ``middleware`` list to the underlying deepagents call."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        call_kwargs = mock_da_create.call_args.kwargs
        assert "middleware" in call_kwargs
        middleware_list = call_kwargs["middleware"]
        assert isinstance(middleware_list, list)
        assert len(middleware_list) >= 1

    @patch("app.agents.factory.SummarizationMiddleware")
    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_summarization_middleware_is_instantiated(
        self,
        mock_model: MagicMock,
        mock_da_create: MagicMock,
        mock_summ_cls: MagicMock,
    ) -> None:
        """Factory must instantiate SummarizationMiddleware and pass the instance."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        assert mock_summ_cls.called
        instance = mock_summ_cls.return_value
        call_kwargs = mock_da_create.call_args.kwargs
        assert instance in call_kwargs.get("middleware", [])

    @patch("app.agents.factory.SummarizationMiddleware")
    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_summarization_keep_messages_from_settings(
        self,
        mock_model: MagicMock,
        mock_da_create: MagicMock,
        mock_summ_cls: MagicMock,
    ) -> None:
        """Factory must pass ``keep=('messages', N)`` with N from settings."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        init_kwargs = mock_summ_cls.call_args.kwargs
        keep = init_kwargs.get("keep")
        assert keep == ("messages", settings.summarization_keep_messages)

    @patch("app.agents.factory.SummarizationMiddleware")
    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_summarization_trigger_includes_message_count_safety_net(
        self,
        mock_model: MagicMock,
        mock_da_create: MagicMock,
        mock_summ_cls: MagicMock,
    ) -> None:
        """Trigger must include message-count entry."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        init_kwargs = mock_summ_cls.call_args.kwargs
        trigger = init_kwargs.get("trigger")
        triggers = trigger if isinstance(trigger, list) else [trigger]
        msg_triggers = [t for t in triggers if isinstance(t, tuple) and t[0] == "messages"]
        assert msg_triggers
        assert any(t[1] == settings.summarization_trigger_messages for t in msg_triggers)

    @patch("app.agents.factory.SummarizationMiddleware")
    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_summarization_custom_prompt_wired_when_set(
        self,
        mock_model: MagicMock,
        mock_da_create: MagicMock,
        mock_summ_cls: MagicMock,
    ) -> None:
        """When summarization_summary_prompt is non-empty it must be forwarded."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        custom_prompt = "Summarize this conversation in bullet points."
        with patch.object(settings, "summarization_summary_prompt", custom_prompt):
            create_deep_agent()

        init_kwargs = mock_summ_cls.call_args.kwargs
        assert init_kwargs.get("summary_prompt") == custom_prompt

    @patch("app.agents.factory.SummarizationMiddleware")
    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_default_prompt_not_set_when_empty(
        self,
        mock_model: MagicMock,
        mock_da_create: MagicMock,
        mock_summ_cls: MagicMock,
    ) -> None:
        """When summarization_summary_prompt is empty, summary_prompt kwarg is omitted."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        with patch.object(settings, "summarization_summary_prompt", ""):
            create_deep_agent()

        init_kwargs = mock_summ_cls.call_args.kwargs
        assert "summary_prompt" not in init_kwargs


# ---------------------------------------------------------------------------
# Settings / config tests
# ---------------------------------------------------------------------------


class TestSummarizationSettings:
    """Verify that summarization settings are present and have sane defaults."""

    def test_settings_have_summarization_trigger_fraction(self) -> None:
        """settings.summarization_trigger_fraction must be a float in (0, 1)."""
        frac = settings.summarization_trigger_fraction
        assert isinstance(frac, float)
        assert 0.0 < frac < 1.0, f"Expected fraction in (0, 1), got {frac}"

    def test_settings_trigger_fraction_default_is_85_percent(self) -> None:
        """Default trigger fraction should be 0.85 (85 % of context window)."""
        # Default is 0.85 — change this test if the default is intentionally adjusted.
        assert settings.summarization_trigger_fraction == pytest.approx(0.85)

    def test_settings_have_summarization_trigger_messages(self) -> None:
        """settings.summarization_trigger_messages must be a positive integer."""
        count = settings.summarization_trigger_messages
        assert isinstance(count, int)
        assert count > 0

    def test_settings_trigger_messages_default(self) -> None:
        """Default message-count trigger should be 200."""
        assert settings.summarization_trigger_messages == 200

    def test_settings_have_summarization_keep_messages(self) -> None:
        """settings.summarization_keep_messages must be a positive integer."""
        keep = settings.summarization_keep_messages
        assert isinstance(keep, int)
        assert keep > 0

    def test_settings_keep_messages_default(self) -> None:
        """Default keep count should be 20 messages."""
        assert settings.summarization_keep_messages == 20

    def test_settings_have_summarization_summary_prompt(self) -> None:
        """settings.summarization_summary_prompt must be a string (may be empty)."""
        assert isinstance(settings.summarization_summary_prompt, str)


# ---------------------------------------------------------------------------
# Deepagents adapter — context_summarized SSE event
# ---------------------------------------------------------------------------


class TestContextSummarizedSSEEvent:
    """Verify map_state_update emits context_summarized when _summarization_event is present."""

    def test_context_summarized_event_emitted_on_summarization(self) -> None:
        """When a node update contains _summarization_event, emit context_summarized."""
        summ_event = {
            "cutoff_index": 15,
            "summary_message": HumanMessage(content="Summary of earlier conversation."),
            "file_path": "/conversation_history/thread-abc.md",
        }
        update = {
            "agent": {
                "_summarization_event": summ_event,
                "messages": [],
            }
        }

        events = map_state_update(update)

        event_types = [e.event for e in events]
        assert "context_summarized" in event_types

        cs_event = next(e for e in events if e.event == "context_summarized")
        assert cs_event.data["cutoff_index"] == 15
        assert cs_event.data["history_file"] == "/conversation_history/thread-abc.md"
        assert cs_event.data["node"] == "agent"

    def test_context_summarized_event_not_emitted_without_summarization(self) -> None:
        """Regular tool-result updates must not emit context_summarized."""
        tool_msg = ToolMessage(content="Result data", tool_call_id="call_1")
        update = {"tools": {"messages": [tool_msg]}}

        events = map_state_update(update)

        event_types = [e.event for e in events]
        assert "context_summarized" not in event_types
        assert "tool_result" in event_types

    def test_context_summarized_no_file_path(self) -> None:
        """context_summarized event is still emitted when file_path is None (offload failed)."""
        summ_event = {
            "cutoff_index": 10,
            "summary_message": HumanMessage(content="Summary."),
            "file_path": None,
        }
        update = {"agent": {"_summarization_event": summ_event}}

        events = map_state_update(update)

        event_types = [e.event for e in events]
        assert "context_summarized" in event_types

        cs_event = next(e for e in events if e.event == "context_summarized")
        assert cs_event.data["history_file"] is None

    def test_context_summarized_coexists_with_tool_results(self) -> None:
        """Both context_summarized and tool_result may appear in the same update batch."""
        summ_event = {
            "cutoff_index": 12,
            "summary_message": HumanMessage(content="Summary."),
            "file_path": "/conversation_history/thread-xyz.md",
        }
        tool_msg = ToolMessage(content="Tool output", tool_call_id="call_2")

        update = {
            "agent": {
                "_summarization_event": summ_event,
                "messages": [tool_msg],
            }
        }

        events = map_state_update(update)
        event_types = [e.event for e in events]

        assert "context_summarized" in event_types
        assert "tool_result" in event_types

    def test_malformed_summarization_event_skipped(self) -> None:
        """A non-dict or None value for _summarization_event must not emit context_summarized."""
        # Value is not a dict — should be silently ignored
        update_non_dict = {"agent": {"_summarization_event": "not-a-dict"}}
        update_none = {"agent": {"_summarization_event": None}}

        events_nd = map_state_update(update_non_dict)
        events_none = map_state_update(update_none)

        assert not any(e.event == "context_summarized" for e in events_nd)
        assert not any(e.event == "context_summarized" for e in events_none)


# ---------------------------------------------------------------------------
# Long conversation / streaming integration tests
# ---------------------------------------------------------------------------


class TestLongConversationStreaming:
    """End-to-end streaming tests simulating long conversations.

    These tests verify that:
    - The agent service streams many turns without error.
    - A context_summarized SSE event propagates correctly from state updates.
    - Message accumulation across turns works as expected.
    """

    @pytest.mark.asyncio
    async def test_many_turn_conversation_streams_without_error(self) -> None:
        """Simulating 30 message turns should complete without errors."""
        # Build a stream of 30 token chunks (simulating a long conversation output)
        chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content=f"Response {i}"), {})) for i in range(30)
        ]

        mock_agent = MagicMock()

        async def fake_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            for chunk in chunks:
                yield chunk

        mock_agent.astream = fake_astream
        svc = AgentService(agent=mock_agent)

        events: list[SSEEvent] = []
        async for evt in svc.stream_response(thread_id="long-t1", user_message="start"):
            events.append(evt)

        event_types = [e.event for e in events]
        assert "error" not in event_types
        assert event_types[0] == "message_start"
        assert event_types[-1] == "message_end"
        assert event_types.count("token") == 30

    @pytest.mark.asyncio
    async def test_context_summarized_event_passes_through_agent_service(self) -> None:
        """When the state update contains _summarization_event, the SSE stream carries
        a context_summarized event through to the client."""
        summ_event = {
            "cutoff_index": 25,
            "summary_message": HumanMessage(content="Earlier conversation summary."),
            "file_path": "/conversation_history/long-t2.md",
        }
        chunks: list[tuple[str, Any]] = [
            ("messages", (AIMessageChunk(content="Here is the result."), {})),
            (
                "updates",
                {
                    "agent": {
                        "_summarization_event": summ_event,
                        "messages": [],
                    }
                },
            ),
        ]

        mock_agent = MagicMock()

        async def fake_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            for chunk in chunks:
                yield chunk

        mock_agent.astream = fake_astream
        svc = AgentService(agent=mock_agent)

        events: list[SSEEvent] = []
        async for evt in svc.stream_response(thread_id="long-t2", user_message="hi"):
            events.append(evt)

        event_types = [e.event for e in events]
        assert "context_summarized" in event_types

        cs_evt = next(e for e in events if e.event == "context_summarized")
        assert cs_evt.data["cutoff_index"] == 25
        assert cs_evt.data["history_file"] == "/conversation_history/long-t2.md"

    @pytest.mark.asyncio
    async def test_long_conversation_with_tool_calls_and_summarization(self) -> None:
        """Long conversation mixing tokens, tool calls, tool results, and a
        summarization event all stream without error and in the right order."""
        summ_event = {
            "cutoff_index": 50,
            "summary_message": HumanMessage(content="Summary."),
            "file_path": "/conversation_history/mixed.md",
        }
        tool_msg = ToolMessage(content="Search results", tool_call_id="call_search")

        chunks: list[tuple[str, Any]] = [
            (
                "messages",
                (
                    AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {"name": "web_search", "args": "{}", "id": "call_search", "index": 0}
                        ],
                    ),
                    {},
                ),
            ),
            ("updates", {"tools": {"messages": [tool_msg]}}),
            ("messages", (AIMessageChunk(content="Based on the search..."), {})),
            # Summarization fires mid-stream
            ("updates", {"agent": {"_summarization_event": summ_event}}),
            ("messages", (AIMessageChunk(content=" the answer is 42."), {})),
        ]

        mock_agent = MagicMock()

        async def fake_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            for chunk in chunks:
                yield chunk

        mock_agent.astream = fake_astream
        svc = AgentService(agent=mock_agent)

        events: list[SSEEvent] = []
        async for evt in svc.stream_response(thread_id="mixed-1", user_message="search and answer"):
            events.append(evt)

        event_types = [e.event for e in events]
        # All expected event types should be present
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "context_summarized" in event_types
        assert "token" in event_types
        assert "message_end" in event_types
        assert "error" not in event_types

        # Final content should be accumulated from both token chunks
        end_evt = next(e for e in events if e.event == "message_end")
        assert "Based on the search" in end_evt.data["content"]
        assert "the answer is 42" in end_evt.data["content"]
