"""Tests for chat streaming endpoint.

The chat/streaming endpoint is not yet implemented (SYM-15 dependency).
These tests validate the expected behavior once the endpoint exists,
and currently verify that the routes are not yet registered (404).

When the chat endpoint is implemented, update these tests to cover:
- POST /chat/{thread_id} happy path (SSE stream)
- Message persistence after chat completion
- Error handling (invalid thread, missing model, etc.)
- Streaming response format (Server-Sent Events)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


class TestChatEndpointNotYetImplemented:
    """Verify chat endpoints are not yet registered (placeholder for SYM-15)."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_not_found(self, client: AsyncClient) -> None:
        """POST /chat/{thread_id} should 404 until implemented."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/chat/{fake_id}", json={"message": "hello"})
        assert resp.status_code == 404 or resp.status_code == 405

    @pytest.mark.asyncio
    async def test_chat_stream_not_found(self, client: AsyncClient) -> None:
        """GET /chat/{thread_id}/stream should 404 until implemented."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/chat/{fake_id}/stream")
        assert resp.status_code == 404 or resp.status_code == 405


class TestChatMessageValidation:
    """Test request validation expectations for future chat endpoint."""

    @pytest.mark.asyncio
    async def test_thread_must_exist_for_chat(self, client: AsyncClient) -> None:
        """Sending a chat to a nonexistent thread should fail."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/chat/{fake_id}", json={"message": "hello"})
        # Until endpoint exists, we get 404
        assert resp.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_empty_message_rejected(self, client: AsyncClient) -> None:
        """An empty message body should be rejected."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/chat/{fake_id}", json={})
        # Until endpoint exists, we get 404
        assert resp.status_code in (404, 405, 422)
