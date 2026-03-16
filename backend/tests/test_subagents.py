"""Tests for subagent coordination via deepagents subagents= parameter (SYM-79).

Covers:
- Subagent configuration building
- Factory integration with subagents= parameter
- Subagent namespace extraction from V2 streaming events
- SSE event mapping for sub_agent_start/progress/end events
- Backwards compatibility (standalone agent without subagents)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from app.agents.deepagents_adapter import extract_subagent_namespace
from app.agents.subagents import (
    SUBAGENT_DESCRIPTIONS,
    SUBAGENT_TYPES,
    build_subagent_configs,
)
from app.services.agent_service import AgentService
from app.services.sse import SSEEvent

# ---------------------------------------------------------------------------
# Subagent configuration tests
# ---------------------------------------------------------------------------


class TestSubagentConfigs:
    """Tests for build_subagent_configs()."""

    def test_default_configs_include_all_types(self) -> None:
        configs = build_subagent_configs()
        names = [c["name"] for c in configs]
        assert "researcher" in names
        assert "coder" in names
        assert "writer" in names

    def test_default_configs_count(self) -> None:
        configs = build_subagent_configs()
        assert len(configs) == len(SUBAGENT_TYPES)

    def test_each_config_has_required_keys(self) -> None:
        configs = build_subagent_configs()
        for config in configs:
            assert "name" in config
            assert "description" in config
            assert "model" in config
            assert "system_prompt" in config
            assert "tools" in config

    def test_custom_model_name(self) -> None:
        configs = build_subagent_configs(model_name="gpt-4o")
        for config in configs:
            assert config["model"] == "gpt-4o"

    def test_model_kwargs_forwarded(self) -> None:
        kwargs = {"temperature": 0.5}
        configs = build_subagent_configs(model_kwargs=kwargs)
        for config in configs:
            assert config["model_kwargs"] == kwargs

    def test_no_model_kwargs_when_none(self) -> None:
        configs = build_subagent_configs()
        for config in configs:
            assert "model_kwargs" not in config

    def test_custom_subagent_types(self) -> None:
        configs = build_subagent_configs(subagent_types=["researcher"])
        assert len(configs) == 1
        assert configs[0]["name"] == "researcher"

    def test_descriptions_are_meaningful(self) -> None:
        for agent_type in SUBAGENT_TYPES:
            desc = SUBAGENT_DESCRIPTIONS[agent_type]
            assert len(desc) > 20, f"{agent_type} description too short"

    def test_system_prompts_are_non_empty(self) -> None:
        configs = build_subagent_configs()
        for config in configs:
            assert len(config["system_prompt"]) > 100

    def test_tools_are_non_empty_lists(self) -> None:
        configs = build_subagent_configs()
        for config in configs:
            assert isinstance(config["tools"], list)
            assert len(config["tools"]) > 0

    def test_tools_are_tool_objects(self) -> None:
        """All tool entries in every config should be BaseTool instances, not strings.

        The deepagents SubAgent spec requires ``tools: Sequence[BaseTool | Callable | dict]``.
        Passing plain strings causes an AttributeError in ToolNode at construction time.
        """
        from langchain_core.tools import BaseTool

        configs = build_subagent_configs()
        for config in configs:
            for tool in config["tools"]:
                assert isinstance(tool, BaseTool), (
                    f"Expected BaseTool instance, got {type(tool)!r}. "
                    "Tool names must be resolved to BaseTool instances before being "
                    "passed to the deepagents framework."
                )

    def test_empty_subagent_types_falls_back_to_defaults(self) -> None:
        """An empty list is falsy, so it falls back to the default SUBAGENT_TYPES."""
        configs = build_subagent_configs(subagent_types=[])
        # [] is falsy → `subagent_types or SUBAGENT_TYPES` returns SUBAGENT_TYPES
        assert len(configs) == len(SUBAGENT_TYPES)

    def test_unknown_agent_type_uses_fallback_description(self) -> None:
        """An unrecognised agent type should use the '<name> specialist' fallback."""
        configs = build_subagent_configs(subagent_types=["custom_specialist"])
        assert len(configs) == 1
        assert configs[0]["description"] == "custom_specialist specialist"

    def test_unknown_agent_type_uses_all_tools(self) -> None:
        """An unrecognised agent type has no specific tool list; all tools are used."""
        from app.agents.tools import TOOL_REGISTRY

        configs = build_subagent_configs(subagent_types=["custom_specialist"])
        # Tools are returned as BaseTool objects; compare by count and id since
        # StructuredTool instances are not hashable.
        tools = configs[0]["tools"]
        registry_tools = list(TOOL_REGISTRY.values())
        assert len(tools) == len(registry_tools)
        tool_ids = {id(t) for t in tools}
        assert all(id(rt) in tool_ids for rt in registry_tools)

    def test_config_name_matches_requested_type(self) -> None:
        """Each config's name field must match its corresponding subagent type."""
        types = ["researcher", "coder"]
        configs = build_subagent_configs(subagent_types=types)
        assert [c["name"] for c in configs] == types


# ---------------------------------------------------------------------------
# Namespace extraction tests
# ---------------------------------------------------------------------------


class TestExtractSubagentNamespace:
    """Tests for extract_subagent_namespace()."""

    def test_none_namespace_returns_none(self) -> None:
        assert extract_subagent_namespace(None) is None

    def test_empty_tuple_returns_none(self) -> None:
        assert extract_subagent_namespace(()) is None

    def test_researcher_namespace(self) -> None:
        ns = ("researcher:abc123",)
        assert extract_subagent_namespace(ns) == "researcher"

    def test_coder_namespace(self) -> None:
        ns = ("coder:xyz789",)
        assert extract_subagent_namespace(ns) == "coder"

    def test_writer_namespace(self) -> None:
        ns = ("writer:def456",)
        assert extract_subagent_namespace(ns) == "writer"

    def test_tools_namespace_is_filtered(self) -> None:
        """Internal 'tools' node should not be treated as a subagent."""
        ns = ("tools:abc123",)
        assert extract_subagent_namespace(ns) is None

    def test_agent_namespace_is_filtered(self) -> None:
        """Internal 'agent' node should not be treated as a subagent."""
        ns = ("agent:abc123",)
        assert extract_subagent_namespace(ns) is None

    def test_interrupt_namespace_is_filtered(self) -> None:
        ns = ("__interrupt__:abc123",)
        assert extract_subagent_namespace(ns) is None

    def test_name_without_colon(self) -> None:
        ns = ("researcher",)
        assert extract_subagent_namespace(ns) == "researcher"

    def test_non_string_element_returns_none(self) -> None:
        ns = (42,)  # type: ignore[assignment]
        assert extract_subagent_namespace(ns) is None

    def test_empty_string_namespace_returns_none(self) -> None:
        """An element that is an empty string should produce None, not an empty name."""
        ns = ("",)
        assert extract_subagent_namespace(ns) is None

    def test_colon_only_namespace_returns_none(self) -> None:
        """An element like ':abc123' splits to name='', which should return None."""
        ns = (":abc123",)
        assert extract_subagent_namespace(ns) is None

    def test_multi_element_namespace_uses_first(self) -> None:
        """Only the first tuple element is inspected for the subagent name."""
        ns = ("researcher:abc123", "other:xyz")
        assert extract_subagent_namespace(ns) == "researcher"

    def test_multi_element_namespace_filters_internal(self) -> None:
        """Internal node names are filtered even when the tuple has multiple elements."""
        ns = ("tools:abc123", "researcher:xyz")
        assert extract_subagent_namespace(ns) is None


# ---------------------------------------------------------------------------
# Factory integration tests
# ---------------------------------------------------------------------------


class TestFactorySubagentIntegration:
    """Tests for create_deep_agent with subagents= parameter."""

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_default_creates_subagents(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """By default, subagents should be passed to deepagents."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()
        call_kwargs = mock_da_create.call_args.kwargs
        assert "subagents" in call_kwargs
        assert len(call_kwargs["subagents"]) == 3

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_disable_subagents(self, mock_model: MagicMock, mock_da_create: MagicMock) -> None:
        """enable_subagents=False should not pass subagents."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent(enable_subagents=False)
        call_kwargs = mock_da_create.call_args.kwargs
        assert "subagents" not in call_kwargs

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_explicit_subagents_override(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """Explicit subagents= should override default configs."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        custom = [{"name": "custom", "model": "gpt-4o", "system_prompt": "hi", "tools": []}]
        create_deep_agent(subagents=custom)
        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs["subagents"] == custom

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_assistant_type_still_works_with_subagents(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """assistant_type should still set the prompt even with subagents enabled."""
        from app.agents.factory import create_deep_agent
        from app.agents.prompts import RESEARCHER_SYSTEM_PROMPT

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent(assistant_type="researcher")
        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs["system_prompt"] == RESEARCHER_SYSTEM_PROMPT
        assert "subagents" in call_kwargs


# ---------------------------------------------------------------------------
# Streaming SSE event tests for subagent events
# ---------------------------------------------------------------------------


def _make_v2_mock_agent(
    stream_chunks: list[tuple[str, Any, tuple[str, ...] | None]],
) -> MagicMock:
    """Create a mock agent whose ``astream()`` yields V2-style events.

    Each event is simulated as an object with ``event``, ``data``, and ``ns``
    attributes, matching the V2 streaming contract.
    """
    mock_agent = MagicMock()

    async def fake_astream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        for mode, data, ns in stream_chunks:
            event_obj = MagicMock()
            event_obj.event = mode
            event_obj.data = data
            event_obj.ns = ns
            yield event_obj

    mock_agent.astream = fake_astream
    return mock_agent


async def _collect_events(svc: AgentService, **kwargs: Any) -> list[SSEEvent]:
    """Collect all SSE events from stream_response."""
    events: list[SSEEvent] = []
    async for evt in svc.stream_response(**kwargs):
        events.append(evt)
    return events


class TestSubagentSSEEvents:
    """Tests for subagent lifecycle SSE events during streaming."""

    @pytest.mark.asyncio
    async def test_subagent_start_event_emitted(self) -> None:
        """When a subagent namespace appears, sub_agent_start should be emitted."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            (
                "messages",
                (AIMessageChunk(content="Researching..."), {}),
                ("researcher:abc123",),
            ),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="research this")

        start_events = [e for e in events if e.event == "sub_agent_start"]
        assert len(start_events) == 1
        assert start_events[0].data["subagent_name"] == "researcher"

    @pytest.mark.asyncio
    async def test_subagent_progress_events(self) -> None:
        """Subagent tokens should be wrapped as sub_agent_progress events."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            (
                "messages",
                (AIMessageChunk(content="Finding info..."), {}),
                ("researcher:abc123",),
            ),
            (
                "messages",
                (AIMessageChunk(content=" Done."), {}),
                ("researcher:abc123",),
            ),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="research")

        progress_events = [e for e in events if e.event == "sub_agent_progress"]
        assert len(progress_events) == 2
        assert progress_events[0].data["inner_event"] == "token"
        assert progress_events[0].data["token"] == "Finding info..."

    @pytest.mark.asyncio
    async def test_subagent_end_event_emitted(self) -> None:
        """After the stream loop, sub_agent_end should be emitted for active subagents."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            (
                "messages",
                (AIMessageChunk(content="Done"), {}),
                ("researcher:abc123",),
            ),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="go")

        end_events = [e for e in events if e.event == "sub_agent_end"]
        assert len(end_events) == 1
        assert end_events[0].data["subagent_name"] == "researcher"

    @pytest.mark.asyncio
    async def test_supervisor_events_not_wrapped(self) -> None:
        """Supervisor-level events (ns=None) should not be wrapped as subagent events."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            (
                "messages",
                (AIMessageChunk(content="Hello"), {}),
                None,
            ),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="hi")

        token_events = [e for e in events if e.event == "token"]
        assert len(token_events) == 1
        assert token_events[0].data["token"] == "Hello"

        # No subagent events
        sub_events = [e for e in events if e.event.startswith("sub_agent")]
        assert len(sub_events) == 0

    @pytest.mark.asyncio
    async def test_mixed_supervisor_and_subagent_events(self) -> None:
        """Both supervisor and subagent events should be handled correctly."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            ("messages", (AIMessageChunk(content="Let me delegate."), {}), None),
            ("messages", (AIMessageChunk(content="Searching..."), {}), ("researcher:r1",)),
            ("messages", (AIMessageChunk(content="Here are results."), {}), None),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="help")

        event_types = [e.event for e in events]
        assert "token" in event_types
        assert "sub_agent_start" in event_types
        assert "sub_agent_progress" in event_types
        assert "sub_agent_end" in event_types
        assert "message_end" in event_types

        # Supervisor tokens contribute to full_content
        end_evt = next(e for e in events if e.event == "message_end")
        assert "Let me delegate." in end_evt.data["content"]
        assert "Here are results." in end_evt.data["content"]

    @pytest.mark.asyncio
    async def test_multiple_subagents_tracked(self) -> None:
        """Multiple subagents should each get start/end events."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            ("messages", (AIMessageChunk(content="Research"), {}), ("researcher:r1",)),
            ("messages", (AIMessageChunk(content="Code"), {}), ("coder:c1",)),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="do both")

        start_events = [e for e in events if e.event == "sub_agent_start"]
        end_events = [e for e in events if e.event == "sub_agent_end"]
        assert len(start_events) == 2
        assert len(end_events) == 2

        start_names = {e.data["subagent_name"] for e in start_events}
        assert start_names == {"researcher", "coder"}

    @pytest.mark.asyncio
    async def test_subagent_start_emitted_only_once(self) -> None:
        """sub_agent_start should only fire once per subagent, not per chunk."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            ("messages", (AIMessageChunk(content="A"), {}), ("researcher:r1",)),
            ("messages", (AIMessageChunk(content="B"), {}), ("researcher:r1",)),
            ("messages", (AIMessageChunk(content="C"), {}), ("researcher:r1",)),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="go")

        start_events = [e for e in events if e.event == "sub_agent_start"]
        assert len(start_events) == 1

    @pytest.mark.asyncio
    async def test_subagent_tool_result_wrapped(self) -> None:
        """Tool results from subagents should be wrapped as sub_agent_progress."""
        tool_msg = ToolMessage(content="Search result", tool_call_id="call_1")
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            ("messages", (AIMessageChunk(content="Searching"), {}), ("researcher:r1",)),
            ("updates", {"tools": {"messages": [tool_msg]}}, ("researcher:r1",)),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="search")

        progress_events = [e for e in events if e.event == "sub_agent_progress"]
        tool_progress = [e for e in progress_events if e.data.get("inner_event") == "tool_result"]
        assert len(tool_progress) == 1
        assert tool_progress[0].data["output"] == "Search result"

    @pytest.mark.asyncio
    async def test_tools_namespace_not_treated_as_subagent(self) -> None:
        """Events from the 'tools' namespace should be treated as supervisor events."""
        tool_msg = ToolMessage(content="Result", tool_call_id="call_1")
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            ("updates", {"tools": {"messages": [tool_msg]}}, ("tools:abc123",)),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="go")

        # Should not have any subagent events
        sub_events = [e for e in events if e.event.startswith("sub_agent")]
        assert len(sub_events) == 0

        # Should have a regular tool_result event
        tool_events = [e for e in events if e.event == "tool_result"]
        assert len(tool_events) == 1


# ---------------------------------------------------------------------------
# Backwards compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardsCompatibility:
    """Ensure existing agent type selection still works."""

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_disable_subagents_creates_standalone_agent(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """With enable_subagents=False, no subagents should be passed."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent(assistant_type="researcher", enable_subagents=False)
        call_kwargs = mock_da_create.call_args.kwargs
        assert "subagents" not in call_kwargs

    @pytest.mark.asyncio
    async def test_no_subagent_events_without_namespace(self) -> None:
        """Streams without namespace info should work as before."""
        chunks: list[tuple[str, Any, tuple[str, ...] | None]] = [
            ("messages", (AIMessageChunk(content="Hello world"), {}), None),
        ]
        svc = AgentService(agent=_make_v2_mock_agent(chunks))
        events = await _collect_events(svc, thread_id="t1", user_message="hi")

        event_types = [e.event for e in events]
        assert "message_start" in event_types
        assert "token" in event_types
        assert "message_end" in event_types
        # No subagent events
        assert "sub_agent_start" not in event_types
        assert "sub_agent_progress" not in event_types
        assert "sub_agent_end" not in event_types
