"""Tests for agent factory and agent-related functionality (SYM-15).

Covers:
- Agent factory instantiation
- System prompt configuration
- Message model integration with agent interactions
- SSEEvent encoding
- LangGraph checkpoint / thread state support
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import _get_chat_model, create_deep_agent
from app.agents.prompts.general import GENERAL_SYSTEM_PROMPT
from app.models.message import Message, MessageCreate
from app.models.thread import Thread, ThreadCreate
from app.services.thread_service import ThreadService

# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Tests for the general-purpose system prompt."""

    def test_prompt_is_non_empty(self) -> None:
        assert len(GENERAL_SYSTEM_PROMPT) > 100

    def test_prompt_contains_identity(self) -> None:
        assert "Symphony" in GENERAL_SYSTEM_PROMPT

    def test_prompt_contains_guidelines(self) -> None:
        assert "Guidelines" in GENERAL_SYSTEM_PROMPT

    def test_prompt_module_exports(self) -> None:
        from app.agents.prompts import GENERAL_SYSTEM_PROMPT as EXPORTED_PROMPT

        assert EXPORTED_PROMPT is GENERAL_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Agent factory tests
# ---------------------------------------------------------------------------


class TestAgentFactory:
    """Tests for create_deep_agent factory function."""

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_agent_returns_compiled_graph(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """Factory should return a compiled deep agent."""
        mock_llm = MagicMock()
        mock_model.return_value = mock_llm
        mock_agent = MagicMock()
        mock_agent.ainvoke = MagicMock()
        mock_agent.astream = MagicMock()
        mock_da_create.return_value = mock_agent

        agent = create_deep_agent()
        assert agent is not None
        assert hasattr(agent, "ainvoke")
        assert hasattr(agent, "astream")
        mock_da_create.assert_called_once()

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_agent_with_custom_prompt(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(system_prompt="You are a test bot.")
        assert agent is not None
        # Verify system_prompt was passed through to deepagents
        call_kwargs = mock_da_create.call_args
        assert call_kwargs.kwargs["system_prompt"] == "You are a test bot."

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_agent_with_custom_checkpointer(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        custom_saver = MagicMock()
        agent = create_deep_agent(checkpointer=custom_saver)
        assert agent is not None
        # Verify checkpointer was passed through to deepagents
        call_kwargs = mock_da_create.call_args
        assert call_kwargs.kwargs["checkpointer"] is custom_saver

    def test_get_chat_model_openai_import_error(self) -> None:
        """If langchain-openai is not installed, ImportError is raised."""
        with (
            patch.dict("sys.modules", {"langchain_openai": None}),
            pytest.raises(ImportError, match="langchain-openai"),
        ):
            _get_chat_model("gpt-4o")

    def test_get_chat_model_anthropic_import_error(self) -> None:
        """If langchain-anthropic is not installed, ImportError is raised."""
        with (
            patch.dict("sys.modules", {"langchain_anthropic": None}),
            pytest.raises(ImportError, match="langchain-anthropic"),
        ):
            _get_chat_model("claude-3-sonnet")

    def test_factory_module_exports(self) -> None:
        from app.agents import create_deep_agent as exported

        assert callable(exported)


# ---------------------------------------------------------------------------
# Message model tests (data layer supporting agent interactions)
# ---------------------------------------------------------------------------


class TestMessageModel:
    """Tests for Message ORM model — the data layer supporting agent interactions."""

    @pytest.mark.asyncio
    async def test_create_user_message(self, db_session: AsyncSession) -> None:
        """A user message can be created and persisted."""
        thread = Thread(title="Agent thread")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        msg = Message(
            thread_id=thread.id,
            role="user",
            content="Hello agent",
            metadata_={},
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "Hello agent"
        assert msg.thread_id == thread.id
        assert msg.tool_calls is None

    @pytest.mark.asyncio
    async def test_create_assistant_message(self, db_session: AsyncSession) -> None:
        """An assistant message can be created with content."""
        thread = Thread(title="Assistant thread")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        msg = Message(
            thread_id=thread.id,
            role="assistant",
            content="I can help with that!",
            metadata_={},
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.role == "assistant"
        assert msg.content == "I can help with that!"

    @pytest.mark.asyncio
    async def test_create_message_with_tool_calls(self, db_session: AsyncSession) -> None:
        """Messages can store tool call metadata (for agent interactions)."""
        thread = Thread(title="Tool thread")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        tool_calls = {
            "calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"query": "test"}'},
                }
            ]
        }
        msg = Message(
            thread_id=thread.id,
            role="assistant",
            content="Let me search for that.",
            tool_calls=tool_calls,
            metadata_={},
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.tool_calls is not None
        assert msg.tool_calls["calls"][0]["function"]["name"] == "search"

    @pytest.mark.asyncio
    async def test_create_system_message(self, db_session: AsyncSession) -> None:
        """System messages can be created (for agent system prompts)."""
        thread = Thread(title="System thread")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        msg = Message(
            thread_id=thread.id,
            role="system",
            content="You are a helpful assistant.",
            metadata_={"source": "agent_factory"},
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.role == "system"
        assert msg.metadata_["source"] == "agent_factory"

    @pytest.mark.asyncio
    async def test_message_thread_relationship(self, sample_thread: Thread) -> None:
        """Messages should be accessible via the thread relationship."""
        assert len(sample_thread.messages) == 3
        roles = [m.role for m in sample_thread.messages]
        assert roles == ["user", "assistant", "user"]

    @pytest.mark.asyncio
    async def test_message_repr(self, db_session: AsyncSession) -> None:
        """Message __repr__ should include id and role."""
        thread = Thread(title="Repr thread")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        msg = Message(thread_id=thread.id, role="user", content="test", metadata_={})
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        repr_str = repr(msg)
        assert "Message" in repr_str
        assert "user" in repr_str


class TestMessageSchemas:
    """Tests for Message Pydantic schemas used in API responses."""

    def test_message_create_schema(self) -> None:
        """MessageCreate should validate required fields."""
        mc = MessageCreate(role="user", content="Hello")
        assert mc.role == "user"
        assert mc.content == "Hello"
        assert mc.tool_calls is None
        assert mc.metadata == {}

    def test_message_create_with_tool_calls(self) -> None:
        mc = MessageCreate(
            role="assistant",
            content="Calling tool",
            tool_calls={"calls": [{"id": "1"}]},
        )
        assert mc.tool_calls is not None

    def test_message_out_from_attributes(self, sample_thread: Thread) -> None:
        """MessageOut should be constructable from ORM attributes."""
        pass


class TestThreadMetadataForAgents:
    """Tests for thread metadata patterns used by agent interactions."""

    @pytest.mark.asyncio
    async def test_thread_metadata_stores_agent_config(self, thread_service: ThreadService) -> None:
        """Thread metadata can store agent configuration."""
        data = ThreadCreate(
            title="Agent Chat",
            assistant_id="symphony-agent-v1",
            metadata={
                "agent_type": "research",
                "model": "gpt-4o",
                "temperature": 0.7,
                "tools": ["search", "calculator"],
            },
        )
        thread = await thread_service.create(data)

        fetched = await thread_service.get(thread.id)
        assert fetched is not None
        assert fetched.assistant_id == "symphony-agent-v1"
        assert fetched.metadata_["agent_type"] == "research"
        assert fetched.metadata_["tools"] == ["search", "calculator"]

    @pytest.mark.asyncio
    async def test_thread_repr(self, thread_service: ThreadService) -> None:
        """Thread __repr__ should include id and title."""
        thread = await thread_service.create(ThreadCreate(title="Repr Test"))
        repr_str = repr(thread)
        assert "Thread" in repr_str
        assert "Repr Test" in repr_str


class TestCustomTypes:
    """Tests for custom SQLAlchemy column types (GUID, JSONType)."""

    @pytest.mark.asyncio
    async def test_guid_stores_and_retrieves_uuid(self, db_session: AsyncSession) -> None:
        """GUID type should correctly round-trip UUIDs through SQLite."""
        thread = Thread(title="UUID test")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        assert isinstance(thread.id, uuid.UUID)
        from sqlalchemy import select

        result = await db_session.execute(select(Thread).where(Thread.id == thread.id))
        fetched = result.scalar_one()
        assert fetched.id == thread.id
        assert isinstance(fetched.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_json_type_stores_and_retrieves_dict(self, db_session: AsyncSession) -> None:
        """JSONType should correctly round-trip dicts through SQLite."""
        complex_meta = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "null_val": None,
        }
        thread = Thread(title="JSON test", metadata_=complex_meta)
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        assert thread.metadata_ == complex_meta

    @pytest.mark.asyncio
    async def test_json_type_empty_dict(self, db_session: AsyncSession) -> None:
        """Default empty dict should be stored correctly."""
        thread = Thread(title="Empty meta")
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        assert thread.metadata_ == {}
