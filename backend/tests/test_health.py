"""Tests for the health-check endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Liveness probe
# ---------------------------------------------------------------------------


class TestLivenessProbe:
    """Tests for GET /health and GET /healthz."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self) -> None:
        """GET /health should return 200 with {"status": "ok"}."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_healthz_returns_ok(self) -> None:
        """GET /healthz should return 200 with {"status": "ok"} (legacy)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_health_response_content_type(self) -> None:
        """Health endpoints should return application/json."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Readiness probe
# ---------------------------------------------------------------------------


class TestReadinessProbe:
    """Tests for GET /health/ready."""

    @pytest.mark.asyncio
    async def test_readiness_all_ok(self) -> None:
        """When DB and Redis are healthy, readiness returns status=ok."""
        # Mock the database engine.connect() context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine_connect = AsyncMock()
        mock_engine_connect.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_connect.__aexit__ = AsyncMock(return_value=False)

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()

        with (
            patch("app.api.routes.health.engine") as mock_engine,
            patch("redis.asyncio.from_url", return_value=mock_redis),
        ):
            mock_engine.connect.return_value = mock_engine_connect

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["redis"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_db_failure(self) -> None:
        """When DB is down, readiness returns degraded status."""
        mock_engine_connect = AsyncMock()
        mock_engine_connect.__aenter__ = AsyncMock(side_effect=ConnectionError("DB down"))
        mock_engine_connect.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()

        with (
            patch("app.api.routes.health.engine") as mock_engine,
            patch("redis.asyncio.from_url", return_value=mock_redis),
        ):
            mock_engine.connect.return_value = mock_engine_connect

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert "error" in body["checks"]["database"]
        assert body["checks"]["redis"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_redis_failure(self) -> None:
        """When Redis is down, readiness returns degraded status."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine_connect = AsyncMock()
        mock_engine_connect.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_connect.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.api.routes.health.engine") as mock_engine,
            patch("redis.asyncio.from_url", side_effect=ConnectionError("Redis down")),
        ):
            mock_engine.connect.return_value = mock_engine_connect

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["database"] == "ok"
        assert "error" in body["checks"]["redis"]

    @pytest.mark.asyncio
    async def test_readiness_both_down(self) -> None:
        """When both DB and Redis are down, readiness returns degraded."""
        mock_engine_connect = AsyncMock()
        mock_engine_connect.__aenter__ = AsyncMock(side_effect=ConnectionError("DB down"))
        mock_engine_connect.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.api.routes.health.engine") as mock_engine,
            patch("redis.asyncio.from_url", side_effect=ConnectionError("Redis down")),
        ):
            mock_engine.connect.return_value = mock_engine_connect

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert "error" in body["checks"]["database"]
        assert "error" in body["checks"]["redis"]
