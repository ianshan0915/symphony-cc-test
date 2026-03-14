"""Shared test fixtures — in-memory SQLite async engine for fast tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import app
from app.models.message import Message
from app.models.thread import Thread, ThreadCreate
from app.services.thread_service import ThreadService

# Use an in-memory SQLite database for tests (requires aiosqlite).
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    """Create a temporary async engine for a single test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """Yield a test DB session."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def thread_service(db_session: AsyncSession) -> ThreadService:
    """ThreadService backed by the test DB session."""
    return ThreadService(db_session)


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sample_thread(db_session: AsyncSession) -> Thread:
    """Create and return a sample thread with messages in the test DB."""
    thread = Thread(title="Sample Thread", assistant_id="default", metadata_={})
    db_session.add(thread)
    await db_session.commit()
    await db_session.refresh(thread)

    # Add sample messages
    for _i, (role, content) in enumerate(
        [
            ("user", "Hello, how are you?"),
            ("assistant", "I'm doing well, thanks!"),
            ("user", "Can you help me with something?"),
        ]
    ):
        msg = Message(
            thread_id=thread.id,
            role=role,
            content=content,
            metadata_={},
        )
        db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(thread)
    return thread


@pytest.fixture
async def multiple_threads(thread_service: ThreadService) -> list[Thread]:
    """Create several threads for pagination / listing tests."""
    threads = []
    for i in range(5):
        t = await thread_service.create(ThreadCreate(title=f"Thread {i}"))
        threads.append(t)
    return threads


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP test client with DI overrides for the DB session."""

    async def _override_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
