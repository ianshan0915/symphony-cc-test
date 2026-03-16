"""Tests for persistent memory — AGENTS.md store, API endpoints, and factory
integration (SYM-85).

Covers:
- Middleware: seed, get, and set AGENTS.md in the store
- API: GET /memory and PUT /memory endpoints (auth, response, persistence)
- Factory: memory=["/memories/AGENTS.md"] passed to create_deep_agent
- Persistence: content survives across separate store reads (cross-thread)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from langgraph.store.memory import InMemoryStore

import app.agents.middleware as mw
from app.agents.middleware import (
    AGENTS_MD_KEY,
    AGENTS_MD_NAMESPACE,
    DEFAULT_AGENTS_MD_CONTENT,
    _make_file_data,
    _seed_agents_md_if_missing,
    get_agents_md,
    set_agents_md,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_fresh_store() -> InMemoryStore:
    """Return a clean InMemoryStore for isolation between tests."""
    return InMemoryStore()


def _store_value(content: str) -> dict:
    """Build a store value in StoreBackend format for pre-seeding tests."""
    return _make_file_data(content)


# ---------------------------------------------------------------------------
# Middleware unit tests — AGENTS.md seeding and accessors
# ---------------------------------------------------------------------------


class TestAgentsMdSeed:
    """Tests for _seed_agents_md_if_missing."""

    @pytest.mark.asyncio
    async def test_seed_writes_default_content_when_missing(self) -> None:
        """Seeding into an empty store should write DEFAULT_AGENTS_MD_CONTENT."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            await _seed_agents_md_if_missing()
            item = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)

        assert item is not None
        value = item.value if hasattr(item, "value") else item
        # content is stored as list of lines; join to check for marker text
        assert "Symphony" in "\n".join(value["content"])

    @pytest.mark.asyncio
    async def test_seed_does_not_overwrite_existing_content(self) -> None:
        """Seeding should be a no-op when content already exists."""
        custom = "# My custom AGENTS.md"
        store = await _make_fresh_store()
        await store.aput(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY, _store_value(custom))

        with patch.object(mw, "_memory_store", store):
            await _seed_agents_md_if_missing()
            item = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)

        value = item.value if hasattr(item, "value") else item
        # The content list should reconstruct to the original custom string
        assert "\n".join(value["content"]) == custom

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self) -> None:
        """Calling seed multiple times should result in the same stored value."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            await _seed_agents_md_if_missing()
            await _seed_agents_md_if_missing()
            item = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)

        value = item.value if hasattr(item, "value") else item
        assert "Symphony" in "\n".join(value["content"])

    def test_constants_align_with_storebackend_defaults(self) -> None:
        """AGENTS_MD_NAMESPACE and AGENTS_MD_KEY must match StoreBackend's defaults.

        StoreBackend's legacy namespace resolution falls back to ("filesystem",)
        and uses the file path as the store key.  Our seed/get/set helpers must
        use the same values so that agents can find the seeded file at runtime.
        """
        assert AGENTS_MD_NAMESPACE == ("filesystem",)
        assert AGENTS_MD_KEY == "/memories/AGENTS.md"


class TestAgentsMdAccessors:
    """Tests for get_agents_md and set_agents_md."""

    @pytest.mark.asyncio
    async def test_get_returns_default_when_store_empty(self) -> None:
        """get_agents_md returns the default content when the key is absent."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            content = await get_agents_md()
        assert content == DEFAULT_AGENTS_MD_CONTENT

    @pytest.mark.asyncio
    async def test_set_then_get_roundtrip(self) -> None:
        """Content written via set_agents_md can be read back via get_agents_md."""
        store = await _make_fresh_store()
        expected = "# Roundtrip test\n\nSome context here."
        with patch.object(mw, "_memory_store", store):
            await set_agents_md(expected)
            result = await get_agents_md()
        assert result == expected

    @pytest.mark.asyncio
    async def test_set_overwrites_existing_content(self) -> None:
        """set_agents_md replaces whatever was stored previously."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            await set_agents_md("# First version")
            await set_agents_md("# Second version")
            result = await get_agents_md()
        assert result == "# Second version"

    @pytest.mark.asyncio
    async def test_set_preserves_created_at_timestamp(self) -> None:
        """set_agents_md preserves the original created_at on subsequent writes."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            await set_agents_md("# First version")
            item_after_first = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)
            created_at_first = item_after_first.value["created_at"]

            await set_agents_md("# Second version")
            item_after_second = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)

        assert item_after_second.value["created_at"] == created_at_first

    @pytest.mark.asyncio
    async def test_persistence_across_separate_reads(self) -> None:
        """Content set in one call is available in a subsequent independent call.

        This simulates cross-thread persistence: two agents running in
        different threads share the same store and both see the same memory.
        """
        store = await _make_fresh_store()
        payload = "# Cross-thread memory\n\nUser prefers concise answers."

        # Simulate thread 1 writing memory
        with patch.object(mw, "_memory_store", store):
            await set_agents_md(payload)

        # Simulate thread 2 reading memory (same store, different call context)
        with patch.object(mw, "_memory_store", store):
            result = await get_agents_md()

        assert result == payload

    @pytest.mark.asyncio
    async def test_get_returns_default_on_store_error(self) -> None:
        """get_agents_md falls back to default content when the store raises."""
        broken_store = MagicMock()
        broken_store.aget = AsyncMock(side_effect=RuntimeError("store unavailable"))
        with patch.object(mw, "_memory_store", broken_store):
            result = await get_agents_md()
        assert result == DEFAULT_AGENTS_MD_CONTENT

    @pytest.mark.asyncio
    async def test_stored_value_uses_storebackend_format(self) -> None:
        """Values written by set_agents_md use StoreBackend's file-data format.

        StoreBackend expects {"content": list[str], "created_at": str,
        "modified_at": str}.  This test verifies our helpers write the correct
        structure so deepagents can read the file without errors.
        """
        store = await _make_fresh_store()
        text = "# Hello\n\nWorld"
        with patch.object(mw, "_memory_store", store):
            await set_agents_md(text)
            item = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)

        value = item.value if hasattr(item, "value") else item
        assert isinstance(value["content"], list)
        assert "created_at" in value
        assert "modified_at" in value
        # Content roundtrips correctly
        assert "\n".join(value["content"]) == text


# ---------------------------------------------------------------------------
# API endpoint tests — GET /memory and PUT /memory
# ---------------------------------------------------------------------------


class TestGetMemoryEndpoint:
    """Tests for GET /memory."""

    @pytest.mark.asyncio
    async def test_get_memory_returns_200(self, client: AsyncClient) -> None:
        """GET /memory should return 200 with a content field."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            response = await client.get("/memory")
        assert response.status_code == 200
        body = response.json()
        assert "content" in body

    @pytest.mark.asyncio
    async def test_get_memory_returns_default_when_empty(self, client: AsyncClient) -> None:
        """GET /memory on an empty store returns the default AGENTS.md."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            response = await client.get("/memory")
        assert response.status_code == 200
        assert "Symphony" in response.json()["content"]

    @pytest.mark.asyncio
    async def test_get_memory_returns_seeded_content(self, client: AsyncClient) -> None:
        """GET /memory returns content that was previously written."""
        store = await _make_fresh_store()
        custom = "# My project notes"
        await store.aput(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY, _store_value(custom))
        with patch.object(mw, "_memory_store", store):
            response = await client.get("/memory")
        assert response.status_code == 200
        assert response.json()["content"] == custom

    @pytest.mark.asyncio
    async def test_get_memory_requires_auth(self, unauthed_client: AsyncClient) -> None:
        """GET /memory without a token should return 401."""
        response = await unauthed_client.get("/memory")
        assert response.status_code == 401


class TestPutMemoryEndpoint:
    """Tests for PUT /memory."""

    @pytest.mark.asyncio
    async def test_put_memory_returns_200(self, client: AsyncClient) -> None:
        """PUT /memory should return 200 with the new content."""
        store = await _make_fresh_store()
        new_content = "# Updated AGENTS.md\n\nNew context."
        with patch.object(mw, "_memory_store", store):
            response = await client.put("/memory", json={"content": new_content})
        assert response.status_code == 200
        assert response.json()["content"] == new_content

    @pytest.mark.asyncio
    async def test_put_memory_persists_for_subsequent_get(self, client: AsyncClient) -> None:
        """PUT /memory should persist so a subsequent GET returns the new value."""
        store = await _make_fresh_store()
        new_content = "# Persistent update"
        with patch.object(mw, "_memory_store", store):
            put_resp = await client.put("/memory", json={"content": new_content})
            get_resp = await client.get("/memory")
        assert put_resp.status_code == 200
        assert get_resp.status_code == 200
        assert get_resp.json()["content"] == new_content

    @pytest.mark.asyncio
    async def test_put_memory_requires_content_field(self, client: AsyncClient) -> None:
        """PUT /memory without a 'content' field should return 422."""
        response = await client.put("/memory", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_put_memory_requires_auth(self, unauthed_client: AsyncClient) -> None:
        """PUT /memory without a token should return 401."""
        response = await unauthed_client.put("/memory", json={"content": "x"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_put_memory_allows_empty_string(self, client: AsyncClient) -> None:
        """PUT /memory with empty string content should succeed."""
        store = await _make_fresh_store()
        with patch.object(mw, "_memory_store", store):
            response = await client.put("/memory", json={"content": ""})
        assert response.status_code == 200
        assert response.json()["content"] == ""

    @pytest.mark.asyncio
    async def test_put_memory_rejects_oversized_content(self, client: AsyncClient) -> None:
        """PUT /memory with content exceeding 512 KiB should return 422."""
        oversized = "x" * (524_288 + 1)
        response = await client.put("/memory", json={"content": oversized})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_put_memory_service_unavailable_on_store_error(self, client: AsyncClient) -> None:
        """PUT /memory returns 503 when the store raises unexpectedly."""
        broken_store = MagicMock()
        broken_store.aget = AsyncMock(return_value=None)
        broken_store.aput = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(mw, "_memory_store", broken_store):
            response = await client.put("/memory", json={"content": "x"})
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Factory integration tests — memory= parameter
# ---------------------------------------------------------------------------


class TestFactoryMemoryParameter:
    """Tests that create_deep_agent passes memory=['/memories/AGENTS.md'] to deepagents."""

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_memory_parameter_passed(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """create_deep_agent should pass memory=['/memories/AGENTS.md'] to deepagents."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        call_kwargs = mock_da_create.call_args.kwargs
        assert "memory" in call_kwargs
        assert call_kwargs["memory"] == ["/memories/AGENTS.md"]

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_memory_path_routes_to_storebackend(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """memory path must start with /memories/ so CompositeBackend routes to StoreBackend."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        call_kwargs = mock_da_create.call_args.kwargs
        memory_paths = call_kwargs.get("memory", [])
        assert all(p.startswith("/memories/") for p in memory_paths), (
            "All memory paths must start with /memories/ for StoreBackend routing; "
            f"got {memory_paths}"
        )

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_memory_coexists_with_backend_store_checkpointer(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """memory=, backend=, store=, and checkpointer= should all be passed."""
        from app.agents.factory import create_deep_agent

        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent(
            store=MagicMock(),
            checkpointer=MagicMock(),
            backend=MagicMock(),
        )

        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs["memory"] == ["/memories/AGENTS.md"]
        assert "store" in call_kwargs
        assert "checkpointer" in call_kwargs
        assert "backend" in call_kwargs
