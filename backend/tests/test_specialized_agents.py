"""Tests for specialized agent prompts and factory integration (SYM-31).

Covers:
- Researcher, coder, and writer system prompts
- Agent prompt registry
- Prompt lookup functions
- Tool resolution by agent type
- Prompt caching
- Factory integration with assistant_type parameter
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.factory import (
    _get_agent_type_prompt,
    _get_cached_prompt,
    _prompt_cache,
    _resolve_tools,
    clear_prompt_cache,
    create_deep_agent,
)
from app.agents.prompts import (
    AGENT_PROMPT_REGISTRY,
    VALID_AGENT_TYPES,
    get_prompt_for_agent_type,
    get_tools_for_agent_type,
)
from app.agents.prompts.coder import CODER_SYSTEM_PROMPT, CODER_TOOLS
from app.agents.prompts.general import GENERAL_SYSTEM_PROMPT
from app.agents.prompts.researcher import RESEARCHER_SYSTEM_PROMPT, RESEARCHER_TOOLS
from app.agents.prompts.writer import WRITER_SYSTEM_PROMPT, WRITER_TOOLS


# ---------------------------------------------------------------------------
# Researcher prompt tests
# ---------------------------------------------------------------------------


class TestResearcherPrompt:
    """Tests for the researcher agent system prompt."""

    def test_prompt_is_non_empty(self) -> None:
        assert len(RESEARCHER_SYSTEM_PROMPT) > 200

    def test_prompt_contains_identity(self) -> None:
        assert "Symphony Researcher" in RESEARCHER_SYSTEM_PROMPT

    def test_prompt_emphasizes_search(self) -> None:
        assert "search" in RESEARCHER_SYSTEM_PROMPT.lower()

    def test_prompt_emphasizes_citation(self) -> None:
        assert "cite" in RESEARCHER_SYSTEM_PROMPT.lower() or "citation" in RESEARCHER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_sources(self) -> None:
        assert "Sources" in RESEARCHER_SYSTEM_PROMPT or "sources" in RESEARCHER_SYSTEM_PROMPT

    def test_researcher_tools_defined(self) -> None:
        assert isinstance(RESEARCHER_TOOLS, list)
        assert "web_search" in RESEARCHER_TOOLS

    def test_researcher_tools_prioritize_web_search(self) -> None:
        """web_search should be the first tool for researchers."""
        assert RESEARCHER_TOOLS[0] == "web_search"


# ---------------------------------------------------------------------------
# Coder prompt tests
# ---------------------------------------------------------------------------


class TestCoderPrompt:
    """Tests for the coder agent system prompt."""

    def test_prompt_is_non_empty(self) -> None:
        assert len(CODER_SYSTEM_PROMPT) > 200

    def test_prompt_contains_identity(self) -> None:
        assert "Symphony Coder" in CODER_SYSTEM_PROMPT

    def test_prompt_emphasizes_code_quality(self) -> None:
        assert "code" in CODER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_type_hints(self) -> None:
        assert "type hints" in CODER_SYSTEM_PROMPT.lower() or "type hint" in CODER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_testing(self) -> None:
        assert "test" in CODER_SYSTEM_PROMPT.lower()

    def test_coder_tools_defined(self) -> None:
        assert isinstance(CODER_TOOLS, list)
        assert "search_knowledge_base" in CODER_TOOLS

    def test_coder_tools_prioritize_knowledge_base(self) -> None:
        """Knowledge base should be the first tool for coders."""
        assert CODER_TOOLS[0] == "search_knowledge_base"


# ---------------------------------------------------------------------------
# Writer prompt tests
# ---------------------------------------------------------------------------


class TestWriterPrompt:
    """Tests for the writer agent system prompt."""

    def test_prompt_is_non_empty(self) -> None:
        assert len(WRITER_SYSTEM_PROMPT) > 200

    def test_prompt_contains_identity(self) -> None:
        assert "Symphony Writer" in WRITER_SYSTEM_PROMPT

    def test_prompt_emphasizes_clarity(self) -> None:
        assert "clarity" in WRITER_SYSTEM_PROMPT.lower() or "clear" in WRITER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_tone(self) -> None:
        assert "tone" in WRITER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_structure(self) -> None:
        assert "structure" in WRITER_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_audience(self) -> None:
        assert "audience" in WRITER_SYSTEM_PROMPT.lower()

    def test_writer_tools_defined(self) -> None:
        assert isinstance(WRITER_TOOLS, list)
        assert len(WRITER_TOOLS) > 0


# ---------------------------------------------------------------------------
# Prompt distinctness tests
# ---------------------------------------------------------------------------


class TestPromptDistinctness:
    """Each agent type should have a distinct system prompt."""

    def test_all_prompts_are_different(self) -> None:
        prompts = [
            GENERAL_SYSTEM_PROMPT,
            RESEARCHER_SYSTEM_PROMPT,
            CODER_SYSTEM_PROMPT,
            WRITER_SYSTEM_PROMPT,
        ]
        assert len(set(prompts)) == 4, "All four prompts must be unique"

    def test_all_prompts_mention_symphony(self) -> None:
        for prompt in [GENERAL_SYSTEM_PROMPT, RESEARCHER_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, WRITER_SYSTEM_PROMPT]:
            assert "Symphony" in prompt


# ---------------------------------------------------------------------------
# Agent prompt registry tests
# ---------------------------------------------------------------------------


class TestAgentPromptRegistry:
    """Tests for the AGENT_PROMPT_REGISTRY and helper functions."""

    def test_registry_contains_all_types(self) -> None:
        assert "general" in AGENT_PROMPT_REGISTRY
        assert "researcher" in AGENT_PROMPT_REGISTRY
        assert "coder" in AGENT_PROMPT_REGISTRY
        assert "writer" in AGENT_PROMPT_REGISTRY

    def test_valid_agent_types_set(self) -> None:
        assert VALID_AGENT_TYPES == {"general", "researcher", "coder", "writer"}

    def test_registry_entries_have_required_keys(self) -> None:
        for agent_type, entry in AGENT_PROMPT_REGISTRY.items():
            assert "system_prompt" in entry, f"{agent_type} missing system_prompt"
            assert "tools" in entry, f"{agent_type} missing tools"

    def test_general_tools_is_none(self) -> None:
        """General agent should use all tools (tools=None)."""
        assert AGENT_PROMPT_REGISTRY["general"]["tools"] is None

    def test_specialized_types_have_tool_lists(self) -> None:
        for agent_type in ["researcher", "coder", "writer"]:
            tools = AGENT_PROMPT_REGISTRY[agent_type]["tools"]
            assert isinstance(tools, list), f"{agent_type} tools should be a list"
            assert len(tools) > 0, f"{agent_type} should have at least one tool"


# ---------------------------------------------------------------------------
# Prompt lookup function tests
# ---------------------------------------------------------------------------


class TestGetPromptForAgentType:
    """Tests for get_prompt_for_agent_type()."""

    def test_general_returns_general_prompt(self) -> None:
        assert get_prompt_for_agent_type("general") == GENERAL_SYSTEM_PROMPT

    def test_researcher_returns_researcher_prompt(self) -> None:
        assert get_prompt_for_agent_type("researcher") == RESEARCHER_SYSTEM_PROMPT

    def test_coder_returns_coder_prompt(self) -> None:
        assert get_prompt_for_agent_type("coder") == CODER_SYSTEM_PROMPT

    def test_writer_returns_writer_prompt(self) -> None:
        assert get_prompt_for_agent_type("writer") == WRITER_SYSTEM_PROMPT

    def test_unknown_type_falls_back_to_general(self) -> None:
        assert get_prompt_for_agent_type("nonexistent") == GENERAL_SYSTEM_PROMPT

    def test_empty_string_falls_back_to_general(self) -> None:
        assert get_prompt_for_agent_type("") == GENERAL_SYSTEM_PROMPT


class TestGetToolsForAgentType:
    """Tests for get_tools_for_agent_type()."""

    def test_general_returns_none(self) -> None:
        assert get_tools_for_agent_type("general") is None

    def test_researcher_returns_tool_list(self) -> None:
        tools = get_tools_for_agent_type("researcher")
        assert tools == RESEARCHER_TOOLS

    def test_coder_returns_tool_list(self) -> None:
        tools = get_tools_for_agent_type("coder")
        assert tools == CODER_TOOLS

    def test_writer_returns_tool_list(self) -> None:
        tools = get_tools_for_agent_type("writer")
        assert tools == WRITER_TOOLS

    def test_unknown_type_returns_none(self) -> None:
        assert get_tools_for_agent_type("nonexistent") is None


# ---------------------------------------------------------------------------
# Prompt caching tests
# ---------------------------------------------------------------------------


class TestPromptCaching:
    """Tests for prompt caching functionality."""

    def setup_method(self) -> None:
        """Clear caches before each test."""
        clear_prompt_cache()

    def test_cached_prompt_returns_same_string(self) -> None:
        prompt = "You are a test agent."
        result1 = _get_cached_prompt(prompt)
        result2 = _get_cached_prompt(prompt)
        assert result1 is result2  # Same object, not just equal

    def test_different_prompts_cached_separately(self) -> None:
        prompt_a = "Prompt A"
        prompt_b = "Prompt B"
        result_a = _get_cached_prompt(prompt_a)
        result_b = _get_cached_prompt(prompt_b)
        assert result_a != result_b

    def test_agent_type_prompt_cache(self) -> None:
        result1 = _get_agent_type_prompt("researcher")
        result2 = _get_agent_type_prompt("researcher")
        assert result1 == RESEARCHER_SYSTEM_PROMPT
        assert result1 is result2  # lru_cache should return same object

    def test_clear_prompt_cache(self) -> None:
        _get_cached_prompt("test prompt")
        assert len(_prompt_cache) > 0
        clear_prompt_cache()
        assert len(_prompt_cache) == 0

    def test_lru_cache_info(self) -> None:
        """LRU cache should report hits after repeated lookups."""
        clear_prompt_cache()
        _get_agent_type_prompt("coder")
        _get_agent_type_prompt("coder")
        info = _get_agent_type_prompt.cache_info()
        assert info.hits >= 1


# ---------------------------------------------------------------------------
# Tool resolution tests
# ---------------------------------------------------------------------------


class TestToolResolution:
    """Tests for _resolve_tools()."""

    def test_explicit_tools_take_priority(self) -> None:
        mock_tool = MagicMock()
        result = _resolve_tools([mock_tool], "researcher")
        assert result == [mock_tool]

    def test_assistant_type_resolves_tools(self) -> None:
        result = _resolve_tools(None, "researcher")
        tool_names = [t.name for t in result]
        # Should include tools from RESEARCHER_TOOLS that exist in registry
        assert "web_search" in tool_names

    def test_no_type_returns_all_tools(self) -> None:
        result = _resolve_tools(None, None)
        assert len(result) > 0

    def test_general_type_returns_all_tools(self) -> None:
        result = _resolve_tools(None, "general")
        # general has tools=None, should fall through to all tools
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Factory integration tests
# ---------------------------------------------------------------------------


class TestFactoryWithAssistantType:
    """Tests for create_deep_agent with assistant_type parameter."""

    @patch("app.agents.factory._get_chat_model")
    def test_create_researcher_agent(self, mock_model: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_model.return_value = mock_llm

        agent = create_deep_agent(assistant_type="researcher")
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    @patch("app.agents.factory._get_chat_model")
    def test_create_coder_agent(self, mock_model: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_model.return_value = mock_llm

        agent = create_deep_agent(assistant_type="coder")
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    @patch("app.agents.factory._get_chat_model")
    def test_create_writer_agent(self, mock_model: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_model.return_value = mock_llm

        agent = create_deep_agent(assistant_type="writer")
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    @patch("app.agents.factory._get_chat_model")
    def test_explicit_prompt_overrides_assistant_type(self, mock_model: MagicMock) -> None:
        """When both system_prompt and assistant_type are given, system_prompt wins."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_model.return_value = mock_llm

        custom_prompt = "You are a custom agent."
        agent = create_deep_agent(
            system_prompt=custom_prompt,
            assistant_type="researcher",
        )
        assert agent is not None

    @patch("app.agents.factory._get_chat_model")
    def test_unknown_type_falls_back_to_general(self, mock_model: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_model.return_value = mock_llm

        agent = create_deep_agent(assistant_type="nonexistent")
        assert agent is not None


# ---------------------------------------------------------------------------
# Module exports tests
# ---------------------------------------------------------------------------


class TestModuleExports:
    """Tests for module-level exports."""

    def test_prompts_init_exports_all_prompts(self) -> None:
        from app.agents.prompts import (
            CODER_SYSTEM_PROMPT as c,
            GENERAL_SYSTEM_PROMPT as g,
            RESEARCHER_SYSTEM_PROMPT as r,
            WRITER_SYSTEM_PROMPT as w,
        )
        assert all([g, r, c, w])

    def test_prompts_init_exports_registry(self) -> None:
        from app.agents.prompts import AGENT_PROMPT_REGISTRY as reg
        assert len(reg) == 4

    def test_prompts_init_exports_helpers(self) -> None:
        from app.agents.prompts import get_prompt_for_agent_type, get_tools_for_agent_type
        assert callable(get_prompt_for_agent_type)
        assert callable(get_tools_for_agent_type)
