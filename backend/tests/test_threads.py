"""Tests for thread CRUD endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.thread import ThreadCreate
from app.services.thread_service import ThreadService

# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


class TestThreadService:
    """Unit tests for ThreadService."""

    @pytest.mark.asyncio
    async def test_create_thread(self, thread_service: ThreadService) -> None:
        data = ThreadCreate(title="Test thread")
        thread = await thread_service.create(data)
        assert thread.id is not None
        assert thread.title == "Test thread"
        assert thread.is_deleted is False

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, thread_service: ThreadService) -> None:
        threads, total = await thread_service.list()
        assert threads == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_threads_pagination(self, thread_service: ThreadService) -> None:
        for i in range(5):
            await thread_service.create(ThreadCreate(title=f"Thread {i}"))

        threads, total = await thread_service.list(offset=0, limit=3)
        assert len(threads) == 3
        assert total == 5

        threads2, _ = await thread_service.list(offset=3, limit=3)
        assert len(threads2) == 2

    @pytest.mark.asyncio
    async def test_get_thread(self, thread_service: ThreadService) -> None:
        created = await thread_service.create(ThreadCreate(title="Detail"))
        fetched = await thread_service.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "Detail"

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, thread_service: ThreadService) -> None:
        result = await thread_service.get(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_soft_delete(self, thread_service: ThreadService) -> None:
        thread = await thread_service.create(ThreadCreate(title="To delete"))
        deleted = await thread_service.delete(thread.id)
        assert deleted is True

        # Should not appear in get or list
        assert await thread_service.get(thread.id) is None
        _threads, total = await thread_service.list()
        assert total == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, thread_service: ThreadService) -> None:
        result = await thread_service.delete(uuid.uuid4())
        assert result is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestThreadEndpoints:
    """Integration tests for /threads endpoints."""

    @pytest.mark.asyncio
    async def test_create_thread(self, client: AsyncClient) -> None:
        resp = await client.post("/threads", json={"title": "New thread"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "New thread"
        assert "id" in body
        assert body["is_deleted"] is False

    @pytest.mark.asyncio
    async def test_create_thread_minimal(self, client: AsyncClient) -> None:
        resp = await client.post("/threads", json={})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] is None
        assert body["assistant_id"] == "default"

    @pytest.mark.asyncio
    async def test_list_threads(self, client: AsyncClient) -> None:
        # Create two threads
        await client.post("/threads", json={"title": "A"})
        await client.post("/threads", json={"title": "B"})

        resp = await client.get("/threads")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["threads"]) == 2

    @pytest.mark.asyncio
    async def test_list_threads_pagination(self, client: AsyncClient) -> None:
        for i in range(5):
            await client.post("/threads", json={"title": f"T{i}"})

        resp = await client.get("/threads?offset=2&limit=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["threads"]) == 2
        assert body["offset"] == 2
        assert body["limit"] == 2

    @pytest.mark.asyncio
    async def test_get_thread(self, client: AsyncClient) -> None:
        create_resp = await client.post("/threads", json={"title": "Detail"})
        thread_id = create_resp.json()["id"]

        resp = await client.get(f"/threads/{thread_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == thread_id
        assert body["title"] == "Detail"
        assert "messages" in body

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/threads/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_thread(self, client: AsyncClient) -> None:
        create_resp = await client.post("/threads", json={"title": "Delete me"})
        thread_id = create_resp.json()["id"]

        resp = await client.delete(f"/threads/{thread_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Should no longer be retrievable
        get_resp = await client.get(f"/threads/{thread_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_thread(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/threads/{fake_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_liveness(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_healthz_legacy(self, client: AsyncClient) -> None:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
