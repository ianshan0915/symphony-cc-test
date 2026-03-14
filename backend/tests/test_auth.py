"""Tests for JWT authentication and user model."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    create_access_token,
    decode_access_token,
    get_db_session,
    hash_password,
    verify_password,
)
from app.main import app
from app.models.user import User

# ---------------------------------------------------------------------------
# Password hashing tests
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "my-secret-password"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)


# ---------------------------------------------------------------------------
# JWT token tests
# ---------------------------------------------------------------------------


class TestJWT:
    def test_create_and_decode_token(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload.sub == str(user_id)
        assert payload.exp is not None

    def test_expired_token_raises_401(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))
        with pytest.raises(Exception) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401  # type: ignore[union-attr]

    def test_invalid_token_raises_401(self):
        with pytest.raises(Exception) as exc_info:
            decode_access_token("not-a-valid-token")
        assert exc_info.value.status_code == 401  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Auth middleware integration tests
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    @pytest.fixture
    async def authed_client(
        self, db_session: AsyncSession, test_user: User
    ) -> AsyncClient:
        """Client that sends a valid JWT but does NOT override auth dependency."""
        from collections.abc import AsyncGenerator

        async def _override_db_session() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db_session
        # Intentionally NOT overriding get_current_user so real JWT validation runs

        token = create_access_token(test_user.id)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as c:
            yield c

        app.dependency_overrides.clear()

    async def test_health_endpoints_no_auth(self, unauthed_client: AsyncClient):
        """Health endpoints should NOT require authentication."""
        resp = await unauthed_client.get("/health")
        assert resp.status_code == 200

        resp2 = await unauthed_client.get("/healthz")
        assert resp2.status_code == 200

    async def test_protected_endpoint_no_token_returns_401(
        self, unauthed_client: AsyncClient
    ):
        """Protected endpoints return 401/403 when no Bearer token is sent."""
        resp = await unauthed_client.get("/threads")
        assert resp.status_code in (401, 403)

    async def test_protected_endpoint_invalid_token_returns_401(
        self, unauthed_client: AsyncClient
    ):
        """Protected endpoints return 401 for invalid tokens."""
        resp = await unauthed_client.get(
            "/threads", headers={"Authorization": "Bearer bad-token"}
        )
        assert resp.status_code == 401

    async def test_protected_endpoint_valid_token_ok(
        self, authed_client: AsyncClient
    ):
        """Protected endpoints return 200 with a valid JWT."""
        resp = await authed_client.get("/threads")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Request ID header tests
# ---------------------------------------------------------------------------


class TestRequestID:
    async def test_response_includes_request_id(self, client: AsyncClient):
        """Every response should include an X-Request-ID header."""
        resp = await client.get("/health")
        assert "X-Request-ID" in resp.headers
        # Should be a valid UUID
        uuid.UUID(resp.headers["X-Request-ID"])

    async def test_request_id_propagated(self, client: AsyncClient):
        """If the client sends X-Request-ID, the same value is echoed back."""
        custom_id = "my-trace-id-12345"
        resp = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers["X-Request-ID"] == custom_id
