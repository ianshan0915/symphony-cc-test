"""Tests for the /auth/* API endpoints (register, login, refresh, me)."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    create_access_token,
    get_db_session,
    hash_password,
)
from app.main import app
from app.models.user import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def auth_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client with DB override but NO auth override (real JWT flow)."""

    async def _override_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_success(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/register",
            json={"email": "newuser@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, auth_client: AsyncClient):
        payload = {"email": "dup@example.com", "password": "securepass123"}
        resp1 = await auth_client.post("/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = await auth_client.post("/auth/register", json=payload)
        assert resp2.status_code == 409

    async def test_register_short_password(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "short"},
        )
        assert resp.status_code == 422  # validation error

    async def test_register_invalid_email(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "securepass123"},
        )
        assert resp.status_code == 422

    async def test_register_with_token(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/register/token",
            json={"email": "tokenuser@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_success(self, auth_client: AsyncClient, db_session: AsyncSession):
        # Create a user first
        user = User(
            email="login@example.com",
            hashed_password=hash_password("mypassword123"),
        )
        db_session.add(user)
        await db_session.commit()

        resp = await auth_client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "mypassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, auth_client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="login2@example.com",
            hashed_password=hash_password("correctpass"),
        )
        db_session.add(user)
        await db_session.commit()

        resp = await auth_client.post(
            "/auth/login",
            json={"email": "login2@example.com", "password": "wrongpass1"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "whatever123"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me tests
# ---------------------------------------------------------------------------


class TestMe:
    async def test_me_with_valid_token(self, auth_client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="me@example.com",
            hashed_password=hash_password("mypassword123"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        token = create_access_token(user.id)
        resp = await auth_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"

    async def test_me_without_token(self, auth_client: AsyncClient):
        resp = await auth_client.get("/auth/me")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /auth/refresh tests
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_refresh_returns_new_token(
        self, auth_client: AsyncClient, db_session: AsyncSession,
    ):
        user = User(
            email="refresh@example.com",
            hashed_password=hash_password("mypassword123"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        token = create_access_token(user.id)
        resp = await auth_client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
