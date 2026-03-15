"""Tests for the file artifact tools.

Uses an in-memory SQLite database so no external services are required.
"""

from __future__ import annotations

import asyncio
import sys
import types
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Stub out deepagents before it gets imported transitively through app.agents
if "deepagents" not in sys.modules:
    _stub = types.ModuleType("deepagents")
    _stub.create_deep_agent = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["deepagents"] = _stub

from app.db.base import Base
from app.models.file_artifact import FileArtifact

# ---------------------------------------------------------------------------
# Fixtures — in-memory async SQLite engine
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(monkeypatch):
    """Create an in-memory SQLite database with the file_artifacts table."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable WAL mode and foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Monkeypatch the session factory used by the tools
    monkeypatch.setattr("app.agents.tools.file_tools.async_session_factory", factory)

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# Helpers to invoke tools with a fake config carrying a thread_id
_THREAD_ID = str(uuid.uuid4())


def _config(thread_id: str = _THREAD_ID) -> dict:
    return {"configurable": {"thread_id": thread_id}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_file(db_session):
    from app.agents.tools.file_tools import create_file

    result = await create_file.ainvoke(
        {"file_path": "hello.txt", "content": "Hello, world!"},
        config=_config(),
    )
    assert "File created successfully" in result
    assert "hello.txt" in result
    assert "13 bytes" in result


@pytest.mark.asyncio
async def test_create_duplicate_file(db_session):
    from app.agents.tools.file_tools import create_file

    tid = str(uuid.uuid4())
    await create_file.ainvoke(
        {"file_path": "dup.txt", "content": "first"},
        config=_config(tid),
    )
    result = await create_file.ainvoke(
        {"file_path": "dup.txt", "content": "second"},
        config=_config(tid),
    )
    assert "Error" in result
    assert "already exists" in result


@pytest.mark.asyncio
async def test_read_file(db_session):
    from app.agents.tools.file_tools import create_file, read_file

    tid = str(uuid.uuid4())
    await create_file.ainvoke(
        {"file_path": "readme.md", "content": "# Title\nSome content"},
        config=_config(tid),
    )
    result = await read_file.ainvoke(
        {"file_path": "readme.md"},
        config=_config(tid),
    )
    assert "# Title" in result
    assert "Some content" in result


@pytest.mark.asyncio
async def test_read_nonexistent_file(db_session):
    from app.agents.tools.file_tools import read_file

    result = await read_file.ainvoke(
        {"file_path": "nope.txt"},
        config=_config(str(uuid.uuid4())),
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_write_file_creates_new(db_session):
    from app.agents.tools.file_tools import read_file, write_file

    tid = str(uuid.uuid4())
    result = await write_file.ainvoke(
        {"file_path": "new.txt", "content": "brand new"},
        config=_config(tid),
    )
    assert "File written" in result

    content = await read_file.ainvoke(
        {"file_path": "new.txt"},
        config=_config(tid),
    )
    assert "brand new" in content


@pytest.mark.asyncio
async def test_write_file_overwrites(db_session):
    from app.agents.tools.file_tools import read_file, write_file

    tid = str(uuid.uuid4())
    await write_file.ainvoke(
        {"file_path": "over.txt", "content": "version 1"},
        config=_config(tid),
    )
    await write_file.ainvoke(
        {"file_path": "over.txt", "content": "version 2"},
        config=_config(tid),
    )
    content = await read_file.ainvoke(
        {"file_path": "over.txt"},
        config=_config(tid),
    )
    assert "version 2" in content
    assert "version 1" not in content


@pytest.mark.asyncio
async def test_edit_file(db_session):
    from app.agents.tools.file_tools import edit_file, read_file, write_file

    tid = str(uuid.uuid4())
    await write_file.ainvoke(
        {"file_path": "edit.txt", "content": "Hello world, this is a test."},
        config=_config(tid),
    )
    result = await edit_file.ainvoke(
        {"file_path": "edit.txt", "old_text": "world", "new_text": "universe"},
        config=_config(tid),
    )
    assert "File edited" in result

    content = await read_file.ainvoke(
        {"file_path": "edit.txt"},
        config=_config(tid),
    )
    assert "universe" in content
    assert "world" not in content


@pytest.mark.asyncio
async def test_edit_file_not_found(db_session):
    from app.agents.tools.file_tools import edit_file

    result = await edit_file.ainvoke(
        {"file_path": "ghost.txt", "old_text": "a", "new_text": "b"},
        config=_config(str(uuid.uuid4())),
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_edit_file_ambiguous(db_session):
    from app.agents.tools.file_tools import edit_file, write_file

    tid = str(uuid.uuid4())
    await write_file.ainvoke(
        {"file_path": "ambig.txt", "content": "aaa"},
        config=_config(tid),
    )
    result = await edit_file.ainvoke(
        {"file_path": "ambig.txt", "old_text": "a", "new_text": "b"},
        config=_config(tid),
    )
    assert "Error" in result
    assert "3 times" in result


@pytest.mark.asyncio
async def test_delete_file(db_session):
    from app.agents.tools.file_tools import create_file, delete_file, read_file

    tid = str(uuid.uuid4())
    await create_file.ainvoke(
        {"file_path": "temp.txt", "content": "temporary"},
        config=_config(tid),
    )
    result = await delete_file.ainvoke(
        {"file_path": "temp.txt"},
        config=_config(tid),
    )
    assert "File deleted" in result

    read_result = await read_file.ainvoke(
        {"file_path": "temp.txt"},
        config=_config(tid),
    )
    assert "not found" in read_result


@pytest.mark.asyncio
async def test_delete_nonexistent(db_session):
    from app.agents.tools.file_tools import delete_file

    result = await delete_file.ainvoke(
        {"file_path": "nope.txt"},
        config=_config(str(uuid.uuid4())),
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_list_files(db_session):
    from app.agents.tools.file_tools import create_file, list_files, write_file

    tid = str(uuid.uuid4())
    await create_file.ainvoke(
        {"file_path": "alpha.txt", "content": "aaa"},
        config=_config(tid),
    )
    await write_file.ainvoke(
        {"file_path": "beta.md", "content": "# Beta"},
        config=_config(tid),
    )

    result = await list_files.ainvoke(
        {},
        config=_config(tid),
    )
    assert "2 file(s)" in result
    assert "alpha.txt" in result
    assert "beta.md" in result


@pytest.mark.asyncio
async def test_list_files_empty(db_session):
    from app.agents.tools.file_tools import list_files

    result = await list_files.ainvoke(
        {},
        config=_config(str(uuid.uuid4())),
    )
    assert "No files found" in result


@pytest.mark.asyncio
async def test_thread_isolation(db_session):
    """Files in one thread should not be visible in another."""
    from app.agents.tools.file_tools import create_file, list_files, read_file

    tid1 = str(uuid.uuid4())
    tid2 = str(uuid.uuid4())

    await create_file.ainvoke(
        {"file_path": "secret.txt", "content": "thread-1 only"},
        config=_config(tid1),
    )

    # Thread 2 should not see thread 1's file
    result = await read_file.ainvoke(
        {"file_path": "secret.txt"},
        config=_config(tid2),
    )
    assert "not found" in result

    listing = await list_files.ainvoke({}, config=_config(tid2))
    assert "No files found" in listing


@pytest.mark.asyncio
async def test_tool_registry_contains_file_tools():
    """Verify all file tools are registered in TOOL_REGISTRY."""
    from app.agents.tools import TOOL_REGISTRY

    expected = {"create_file", "read_file", "write_file", "edit_file", "delete_file", "list_files"}
    assert expected.issubset(set(TOOL_REGISTRY.keys()))
