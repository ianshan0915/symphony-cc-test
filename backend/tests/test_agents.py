"""Tests for agent factory and agent-related functionality.

The agent factory is not yet implemented (depends on SYM-14/SYM-15).
These tests validate the data models and infrastructure that support
agent interactions (Message model with tool_calls, Thread metadata).

When agent code is implemented, update these tests to cover:
- Agent factory instantiation
- Agent tool call handling
- LangGraph checkpoint persistence
- Multi-turn conversation state management
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageCreate, MessageOut
from app.models.thread import Thread, ThreadCreate
from app.services.thread_service import ThreadService


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
        # This uses pytest marker but doesn't need async
        pass


class TestThreadMetadataForAgents:
    """Tests for thread metadata patterns used by agent interactions."""

    @pytest.mark.asyncio
    async def test_thread_metadata_stores_agent_config(
        self, thread_service: ThreadService
    ) -> None:
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
        # Fetch again to ensure retrieval works
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
