"""Tests for the health-check endpoint."""

from httpx import ASGITransport, AsyncClient

import pytest

from app.main import app


@pytest.mark.asyncio
async def test_healthz_returns_ok() -> None:
    """GET /healthz should return 200 with {"status": "ok"}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
