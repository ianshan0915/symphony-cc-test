"""Tests for assistant configuration endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ASSISTANT_PAYLOAD = {
    "name": "Test Assistant",
    "description": "A test assistant",
    "model": "gpt-4o",
    "system_prompt": "You are a helpful assistant.",
    "tools_enabled": ["web_search"],
    "metadata": {"env": "test"},
    "temperature": 0.7,
}


# ---------------------------------------------------------------------------
# POST /assistants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_assistant(client: AsyncClient):
    response = await client.post("/assistants", json=ASSISTANT_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Assistant"
    assert data["model"] == "gpt-4o"
    assert data["tools_enabled"] == ["web_search"]
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_assistant_minimal(client: AsyncClient):
    response = await client.post("/assistants", json={"name": "Minimal"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Minimal"
    assert data["model"] == "gpt-4o"  # default


@pytest.mark.asyncio
async def test_create_assistant_validation_error(client: AsyncClient):
    response = await client.post("/assistants", json={"name": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /assistants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_assistants_empty(client: AsyncClient):
    response = await client.get("/assistants")
    assert response.status_code == 200
    data = response.json()
    assert data["assistants"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_assistants(client: AsyncClient):
    # Create a few assistants
    for i in range(3):
        await client.post("/assistants", json={"name": f"Assistant {i}"})

    response = await client.get("/assistants")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["assistants"]) == 3


@pytest.mark.asyncio
async def test_list_assistants_pagination(client: AsyncClient):
    for i in range(5):
        await client.post("/assistants", json={"name": f"Paginated {i}"})

    response = await client.get("/assistants?offset=0&limit=2")
    data = response.json()
    assert data["total"] == 5
    assert len(data["assistants"]) == 2


@pytest.mark.asyncio
async def test_list_assistants_default_first(client: AsyncClient):
    """The assistant marked with is_default should appear first in the list."""
    # Create a non-default assistant first
    await client.post(
        "/assistants",
        json={"name": "Regular", "metadata": {"is_default": False}},
    )
    # Create a second non-default assistant
    await client.post(
        "/assistants",
        json={"name": "Another Regular", "metadata": {}},
    )
    # Create the default assistant last (newest created_at)
    await client.post(
        "/assistants",
        json={"name": "The Default", "metadata": {"is_default": True}},
    )

    response = await client.get("/assistants")
    data = response.json()
    assert data["total"] == 3
    # The default assistant should be first regardless of creation order
    first = data["assistants"][0]
    assert first["name"] == "The Default"
    # metadata may be serialized as "metadata" or "metadata_" depending on config
    meta = first.get("metadata") or first.get("metadata_") or {}
    assert meta.get("is_default") is True


# ---------------------------------------------------------------------------
# GET /assistants/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_assistant(client: AsyncClient):
    create_resp = await client.post("/assistants", json=ASSISTANT_PAYLOAD)
    assistant_id = create_resp.json()["id"]

    response = await client.get(f"/assistants/{assistant_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test Assistant"


@pytest.mark.asyncio
async def test_get_assistant_not_found(client: AsyncClient):
    response = await client.get("/assistants/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /assistants/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_assistant(client: AsyncClient):
    create_resp = await client.post("/assistants", json=ASSISTANT_PAYLOAD)
    assistant_id = create_resp.json()["id"]

    response = await client.put(
        f"/assistants/{assistant_id}",
        json={"name": "Updated Name", "temperature": 0.2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["temperature"] == 0.2
    # Unchanged fields remain the same
    assert data["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_update_assistant_not_found(client: AsyncClient):
    response = await client.put(
        "/assistants/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /assistants/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_assistant(client: AsyncClient):
    create_resp = await client.post("/assistants", json={"name": "To Delete"})
    assistant_id = create_resp.json()["id"]

    response = await client.delete(f"/assistants/{assistant_id}")
    assert response.status_code == 204

    # Should not appear in listing anymore
    list_resp = await client.get("/assistants")
    names = [a["name"] for a in list_resp.json()["assistants"]]
    assert "To Delete" not in names


@pytest.mark.asyncio
async def test_delete_assistant_not_found(client: AsyncClient):
    response = await client.delete("/assistants/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
