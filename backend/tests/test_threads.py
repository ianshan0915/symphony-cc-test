"""Tests for thread CRUD endpoints and service layer."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.thread import Thread, ThreadCreate, ThreadUpdate
from app.services.thread_service import ThreadService

# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


class TestThreadServiceCreate:
    """Unit tests for ThreadService.create()."""

    @pytest.mark.asyncio
    async def test_create_thread(self, thread_service: ThreadService) -> None:
        data = ThreadCreate(title="Test thread")
        thread = await thread_service.create(data)
        assert thread.id is not None
        assert thread.title == "Test thread"
        assert thread.is_deleted is False

    @pytest.mark.asyncio
    async def test_create_thread_with_defaults(self, thread_service: ThreadService) -> None:
        """Creating a thread with no title should set defaults."""
        data = ThreadCreate()
        thread = await thread_service.create(data)
        assert thread.title is None
        assert thread.assistant_id == "default"
        assert thread.metadata_ == {}
        assert thread.is_deleted is False

    @pytest.mark.asyncio
    async def test_create_thread_with_custom_assistant(self, thread_service: ThreadService) -> None:
        data = ThreadCreate(title="Custom", assistant_id="gpt-4o")
        thread = await thread_service.create(data)
        assert thread.assistant_id == "gpt-4o"

    @pytest.mark.asyncio
    async def test_create_thread_with_metadata(self, thread_service: ThreadService) -> None:
        data = ThreadCreate(title="Meta", metadata={"key": "value", "count": 42})
        thread = await thread_service.create(data)
        assert thread.metadata_ == {"key": "value", "count": 42}


class TestThreadServiceList:
    """Unit tests for ThreadService.list()."""

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, thread_service: ThreadService) -> None:
        threads, total = await thread_service.list()
        assert threads == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_threads_returns_all(self, thread_service: ThreadService) -> None:
        for i in range(3):
            await thread_service.create(ThreadCreate(title=f"Thread {i}"))
        threads, total = await thread_service.list()
        assert len(threads) == 3
        assert total == 3

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
    async def test_list_excludes_deleted(self, thread_service: ThreadService) -> None:
        """Deleted threads should not appear in list results."""
        t1 = await thread_service.create(ThreadCreate(title="Keep"))
        t2 = await thread_service.create(ThreadCreate(title="Delete"))
        await thread_service.delete(t2.id)

        threads, total = await thread_service.list()
        assert total == 1
        assert threads[0].id == t1.id


class TestThreadServiceGet:
    """Unit tests for ThreadService.get()."""

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
    async def test_get_deleted_thread_returns_none(self, thread_service: ThreadService) -> None:
        thread = await thread_service.create(ThreadCreate(title="Soon gone"))
        await thread_service.delete(thread.id)
        assert await thread_service.get(thread.id) is None

    @pytest.mark.asyncio
    async def test_get_thread_includes_messages(
        self, thread_service: ThreadService, sample_thread: Thread
    ) -> None:
        """get() should eager-load messages."""
        fetched = await thread_service.get(sample_thread.id)
        assert fetched is not None
        assert len(fetched.messages) == 3
        assert fetched.messages[0].role == "user"


class TestThreadServiceUpdate:
    """Unit tests for ThreadService.update()."""

    @pytest.mark.asyncio
    async def test_update_title(self, thread_service: ThreadService) -> None:
        thread = await thread_service.create(ThreadCreate(title="Old"))
        updated = await thread_service.update(thread.id, ThreadUpdate(title="New"))
        assert updated is not None
        assert updated.title == "New"

    @pytest.mark.asyncio
    async def test_update_metadata(self, thread_service: ThreadService) -> None:
        thread = await thread_service.create(ThreadCreate(title="Meta"))
        updated = await thread_service.update(thread.id, ThreadUpdate(metadata={"updated": True}))
        assert updated is not None
        assert updated.metadata_ == {"updated": True}

    @pytest.mark.asyncio
    async def test_update_title_and_metadata(self, thread_service: ThreadService) -> None:
        thread = await thread_service.create(ThreadCreate(title="Both"))
        updated = await thread_service.update(
            thread.id, ThreadUpdate(title="New Title", metadata={"key": "val"})
        )
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.metadata_ == {"key": "val"}

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, thread_service: ThreadService) -> None:
        result = await thread_service.update(uuid.uuid4(), ThreadUpdate(title="Nope"))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_deleted_thread_returns_none(
        self,
        thread_service: ThreadService,
    ) -> None:
        thread = await thread_service.create(ThreadCreate(title="Will delete"))
        await thread_service.delete(thread.id)
        result = await thread_service.update(thread.id, ThreadUpdate(title="Nope"))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_partial_only_title(self, thread_service: ThreadService) -> None:
        """Updating only title should leave metadata unchanged."""
        thread = await thread_service.create(
            ThreadCreate(title="Original", metadata={"keep": "me"})
        )
        updated = await thread_service.update(thread.id, ThreadUpdate(title="Changed"))
        assert updated is not None
        assert updated.title == "Changed"
        assert updated.metadata_ == {"keep": "me"}


class TestThreadServiceDelete:
    """Unit tests for ThreadService.delete()."""

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

    @pytest.mark.asyncio
    async def test_double_delete(self, thread_service: ThreadService) -> None:
        """Deleting an already-deleted thread should return False."""
        thread = await thread_service.create(ThreadCreate(title="Double"))
        assert await thread_service.delete(thread.id) is True
        assert await thread_service.delete(thread.id) is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestThreadEndpointsCreate:
    """Integration tests for POST /threads."""

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
    async def test_create_thread_with_metadata(self, client: AsyncClient) -> None:
        resp = await client.post("/threads", json={"title": "Meta", "metadata": {"key": "value"}})
        assert resp.status_code == 201
        body = resp.json()
        # The response key depends on Pydantic alias config — check both
        metadata_val = body.get("metadata") or body.get("metadata_") or {}
        assert metadata_val == {"key": "value"}

    @pytest.mark.asyncio
    async def test_create_thread_returns_timestamps(self, client: AsyncClient) -> None:
        resp = await client.post("/threads", json={"title": "Timestamps"})
        assert resp.status_code == 201
        body = resp.json()
        assert "created_at" in body
        assert "updated_at" in body


class TestThreadEndpointsList:
    """Integration tests for GET /threads."""

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/threads")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["threads"] == []

    @pytest.mark.asyncio
    async def test_list_threads(self, client: AsyncClient) -> None:
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
    async def test_list_threads_default_pagination(self, client: AsyncClient) -> None:
        """Default offset=0 and limit=20."""
        resp = await client.get("/threads")
        body = resp.json()
        assert body["offset"] == 0
        assert body["limit"] == 20

    @pytest.mark.asyncio
    async def test_list_threads_invalid_offset(self, client: AsyncClient) -> None:
        """Negative offset should be rejected (422)."""
        resp = await client.get("/threads?offset=-1")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_threads_invalid_limit(self, client: AsyncClient) -> None:
        """Limit of 0 should be rejected (422)."""
        resp = await client.get("/threads?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_threads_limit_too_high(self, client: AsyncClient) -> None:
        """Limit over 100 should be rejected (422)."""
        resp = await client.get("/threads?limit=101")
        assert resp.status_code == 422


class TestThreadEndpointsGet:
    """Integration tests for GET /threads/{thread_id}."""

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
        assert isinstance(body["messages"], list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/threads/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_thread_invalid_uuid(self, client: AsyncClient) -> None:
        """Invalid UUID should return 422."""
        resp = await client.get("/threads/not-a-uuid")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_deleted_thread_returns_404(self, client: AsyncClient) -> None:
        """A soft-deleted thread should not be retrievable."""
        create_resp = await client.post("/threads", json={"title": "Ghost"})
        thread_id = create_resp.json()["id"]
        await client.delete(f"/threads/{thread_id}")

        resp = await client.get(f"/threads/{thread_id}")
        assert resp.status_code == 404


class TestThreadEndpointsDelete:
    """Integration tests for DELETE /threads/{thread_id}."""

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

    @pytest.mark.asyncio
    async def test_delete_thread_invalid_uuid(self, client: AsyncClient) -> None:
        resp = await client.delete("/threads/not-a-uuid")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_already_deleted_thread(self, client: AsyncClient) -> None:
        """Deleting an already-deleted thread should return 404."""
        create_resp = await client.post("/threads", json={"title": "Once"})
        thread_id = create_resp.json()["id"]
        await client.delete(f"/threads/{thread_id}")

        resp = await client.delete(f"/threads/{thread_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Health endpoint tests (via shared client)
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Tests for health check endpoints using the shared test client."""

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
