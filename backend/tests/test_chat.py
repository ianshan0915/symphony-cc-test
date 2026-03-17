"""Tests for SSE streaming chat endpoint (SYM-15, SYM-72, SYM-86)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

import app.agents.middleware as mw
from app.models.assistant import AssistantCreate
from app.models.thread import ThreadCreate
from app.services.agent_service import AgentService, SSEEvent
from app.services.assistant_service import AssistantService
from app.services.thread_service import ThreadService

# ---------------------------------------------------------------------------
# SSEEvent unit tests
# ---------------------------------------------------------------------------


class TestSSEEvent:
    """Unit tests for the SSEEvent dataclass."""

    def test_encode_simple_event(self) -> None:
        evt = SSEEvent(event="token", data={"token": "Hello"})
        encoded = evt.encode()
        assert encoded.startswith("event: token\n")
        assert "data: " in encoded
        assert encoded.endswith("\n\n")
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["token"] == "Hello"

    def test_encode_message_start(self) -> None:
        evt = SSEEvent(event="message_start", data={"thread_id": "abc-123"})
        encoded = evt.encode()
        assert "event: message_start" in encoded

    def test_encode_error_event(self) -> None:
        evt = SSEEvent(event="error", data={"error": "Something went wrong"})
        encoded = evt.encode()
        assert "event: error" in encoded
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["error"] == "Something went wrong"

    def test_encode_empty_data(self) -> None:
        evt = SSEEvent(event="message_end", data={})
        encoded = evt.encode()
        assert "data: {}" in encoded


# ---------------------------------------------------------------------------
# Chat endpoint integration tests
# ---------------------------------------------------------------------------


class TestChatStreamEndpoint:
    """Integration tests for POST /chat/stream."""

    @pytest.mark.asyncio
    async def test_chat_stream_missing_message_returns_422(self, client: AsyncClient) -> None:
        """An empty body should return 422 Unprocessable Entity."""
        resp = await client.post("/chat/stream", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_stream_empty_message_returns_422(self, client: AsyncClient) -> None:
        """An empty string message should be rejected."""
        resp = await client.post("/chat/stream", json={"message": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_stream_nonexistent_thread_returns_404(self, client: AsyncClient) -> None:
        """Pointing to a nonexistent thread_id should 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/chat/stream?thread_id={fake_id}",
            json={"message": "hello"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_stream_returns_sse_content_type(
        self,
        client: AsyncClient,
        thread_service: ThreadService,
        db_session,
    ) -> None:
        """The streaming endpoint should return text/event-stream content type."""

        # Create a thread first
        thread = await thread_service.create(ThreadCreate(title="Test chat"))

        # Mock the agent service to return a simple stream
        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(event="token", data={"token": "Hi"})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "Hi",
                    "tool_calls": None,
                },
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            resp = await client.post(
                f"/chat/stream?thread_id={thread.id}",
                json={"message": "hello"},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            # Parse SSE events from response body
            body = resp.text
            assert "event: message_start" in body
            assert "event: token" in body
            assert "event: message_end" in body
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_chat_stream_creates_thread_if_none_given(
        self,
        client: AsyncClient,
        db_session,
    ) -> None:
        """When no thread_id is provided, a new thread should be created."""

        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "Hello!",
                    "tool_calls": None,
                },
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            resp = await client.post(
                "/chat/stream",
                json={"message": "hello world"},
            )
            assert resp.status_code == 200
            body = resp.text
            assert "event: message_start" in body
            assert "event: message_end" in body
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_chat_stream_uses_assistant_id_for_agent_routing(
        self,
        client: AsyncClient,
        db_session,
    ) -> None:
        """When assistant_id is provided, the agent_type from assistant metadata is used."""

        # Create an assistant with agent_type metadata
        assistant_svc = AssistantService(db_session)
        assistant = await assistant_svc.create(
            AssistantCreate(
                name="Test Researcher",
                description="Research assistant",
                model="gpt-4o",
                tools_enabled=[],
                metadata={"agent_type": "researcher", "is_default": False},
            )
        )

        captured_kwargs: dict = {}

        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            captured_kwargs.update(kwargs)
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "Research result",
                    "tool_calls": None,
                },
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            resp = await client.post(
                f"/chat/stream?assistant_id={assistant.id}",
                json={"message": "research this topic"},
            )
            assert resp.status_code == 200
            # Verify the agent routing received the correct assistant_type
            assert captured_kwargs.get("assistant_type") == "researcher"
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_chat_stream_unknown_assistant_id_falls_back(
        self,
        client: AsyncClient,
        db_session,
    ) -> None:
        """An unknown assistant_id should fall back to the default agent (None type)."""

        captured_kwargs: dict = {}

        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            captured_kwargs.update(kwargs)
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={
                    "thread_id": kwargs["thread_id"],
                    "content": "Hello",
                    "tool_calls": None,
                },
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            fake_id = str(uuid.uuid4())
            resp = await client.post(
                f"/chat/stream?assistant_id={fake_id}",
                json={"message": "hello"},
            )
            assert resp.status_code == 200
            # assistant_type should be None (fallback to default)
            assert captured_kwargs.get("assistant_type") is None
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_memory_updated_event_emitted_when_timestamp_changes(
        self,
        client: AsyncClient,
        thread_service: ThreadService,
        db_session,
    ) -> None:
        """memory_updated SSE event is emitted when AGENTS.md timestamp changes."""
        thread = await thread_service.create(ThreadCreate(title="mem test"))

        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={"thread_id": kwargs["thread_id"], "content": "ok", "tool_calls": None},
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            # Patch get_agents_md_modified_at to simulate a timestamp change.
            call_count = 0

            async def fake_modified_at(user_id: str | None = None) -> str:
                nonlocal call_count
                call_count += 1
                return "2026-01-01T00:00:00" if call_count == 1 else "2026-01-01T00:01:00"

            with (
                patch.object(mw, "_memory_store", mw.get_memory_store()),
                patch("app.api.routes.chat.get_agents_md_modified_at", fake_modified_at),
            ):
                resp = await client.post(
                    f"/chat/stream?thread_id={thread.id}",
                    json={"message": "hello"},
                )
            assert resp.status_code == 200
            assert "event: memory_updated" in resp.text
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_memory_updated_event_not_emitted_when_timestamp_unchanged(
        self,
        client: AsyncClient,
        thread_service: ThreadService,
        db_session,
    ) -> None:
        """memory_updated SSE event is NOT emitted when AGENTS.md is unchanged."""
        thread = await thread_service.create(ThreadCreate(title="mem test 2"))

        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={"thread_id": kwargs["thread_id"], "content": "ok", "tool_calls": None},
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            same_ts = "2026-01-01T00:00:00"

            async def fake_modified_at_same(user_id: str | None = None) -> str:
                return same_ts

            with patch("app.api.routes.chat.get_agents_md_modified_at", fake_modified_at_same):
                resp = await client.post(
                    f"/chat/stream?thread_id={thread.id}",
                    json={"message": "hello"},
                )
            assert resp.status_code == 200
            assert "event: memory_updated" not in resp.text
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]

    @pytest.mark.asyncio
    async def test_memory_updated_event_not_emitted_when_timestamp_unavailable(
        self,
        client: AsyncClient,
        thread_service: ThreadService,
        db_session,
    ) -> None:
        """memory_updated is NOT emitted when both timestamps are None (no memory yet)."""
        thread = await thread_service.create(ThreadCreate(title="mem test 3"))

        async def mock_stream(**kwargs) -> AsyncIterator[SSEEvent]:
            yield SSEEvent(event="message_start", data={"thread_id": kwargs["thread_id"]})
            yield SSEEvent(
                event="message_end",
                data={"thread_id": kwargs["thread_id"], "content": "ok", "tool_calls": None},
            )

        from app.services.agent_service import agent_service

        original_stream = agent_service.stream_response
        agent_service.stream_response = mock_stream  # type: ignore[assignment]
        try:
            async def fake_modified_at_none(user_id: str | None = None) -> None:
                return None

            with patch("app.api.routes.chat.get_agents_md_modified_at", fake_modified_at_none):
                resp = await client.post(
                    f"/chat/stream?thread_id={thread.id}",
                    json={"message": "hello"},
                )
            assert resp.status_code == 200
            assert "event: memory_updated" not in resp.text
        finally:
            agent_service.stream_response = original_stream  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Agent service unit tests
# ---------------------------------------------------------------------------


class TestAgentService:
    """Unit tests for the AgentService class."""

    def test_agent_service_default_init(self) -> None:
        svc = AgentService()
        assert svc._agent is None

    def test_agent_service_set_agent(self) -> None:
        svc = AgentService()
        mock_agent = AsyncMock()
        svc.set_agent(mock_agent)
        assert svc._agent is mock_agent

    @pytest.mark.asyncio
    async def test_stream_response_emits_error_on_exception(self) -> None:
        """If the agent raises, an error SSE event should be emitted."""
        svc = AgentService()

        # Create a mock agent whose astream raises
        mock_agent = AsyncMock()
        mock_agent.astream = AsyncMock(side_effect=RuntimeError("LLM down"))
        svc.set_agent(mock_agent)

        events: list[SSEEvent] = []
        async for evt in svc.stream_response(
            thread_id="test-thread",
            user_message="hello",
        ):
            events.append(evt)

        event_types = [e.event for e in events]
        assert "message_start" in event_types
        assert "error" in event_types
        # Should NOT have message_end after an error
        assert "message_end" not in event_types
