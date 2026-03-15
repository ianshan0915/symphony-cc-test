"""File artifact tools for LangGraph agents.

Provides tools to create, read, write, edit, delete, and list file
artifacts that are persisted in the database.  Each file is scoped to a
conversation thread via ``thread_id`` stored in the LangGraph
``RunnableConfig``.

The thread_id is extracted from the RunnableConfig that LangGraph
automatically injects when streaming agents.  For standalone / test
invocations the config can be passed via ``ainvoke(..., config=...)``.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from sqlalchemy import select, update

from app.db.session import async_session_factory
from app.models.file_artifact import FileArtifact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_THREAD_ID = "00000000-0000-0000-0000-000000000000"


def _extract_thread_id(config: Optional[RunnableConfig] = None) -> str:
    """Extract the thread_id from a LangGraph RunnableConfig.

    Falls back to a default UUID if the config is not available (e.g. in
    tests or ad-hoc invocations).
    """
    if config:
        configurable = config.get("configurable") or {}
        tid = configurable.get("thread_id")
        if tid:
            return str(tid)
    return _DEFAULT_THREAD_ID


def _guess_mime_type(file_path: str) -> Optional[str]:
    """Return a MIME type guess based on the file extension."""
    mime, _ = mimetypes.guess_type(file_path)
    return mime


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


@tool
async def create_file(
    file_path: str,
    content: str = "",
    *,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """Create a new file artifact with the given path and optional content.

    Use this tool to create a brand-new file.  If a file at the same path
    already exists in the current thread, the creation will fail — use
    ``write_file`` to overwrite an existing file instead.

    Args:
        file_path: The virtual path for the file (e.g. "report.md", "src/app.py").
        content: Initial content for the file (default empty).
    """
    thread_id = _extract_thread_id(config)

    async with async_session_factory() as session:
        # Check for existing file at this path
        stmt = select(FileArtifact).where(
            FileArtifact.thread_id == uuid.UUID(thread_id),
            FileArtifact.file_path == file_path,
            FileArtifact.is_deleted == False,  # noqa: E712
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return f"Error: File already exists at '{file_path}'. Use write_file to overwrite it."

        artifact = FileArtifact(
            thread_id=uuid.UUID(thread_id),
            file_path=file_path,
            content=content,
            mime_type=_guess_mime_type(file_path),
            metadata_={},
        )
        session.add(artifact)
        await session.commit()

        size = len(content)
        return (
            f"File created successfully: '{file_path}' "
            f"({size} bytes, id={artifact.id})"
        )


@tool
async def write_file(
    file_path: str,
    content: str,
    *,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """Write content to a file, creating it if it doesn't exist or replacing its content if it does.

    Use this tool to save text content to a file artifact.  If the file
    already exists, its content is fully replaced.

    Args:
        file_path: The virtual path for the file (e.g. "output.txt").
        content: The full content to write to the file.
    """
    thread_id = _extract_thread_id(config)
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        stmt = select(FileArtifact).where(
            FileArtifact.thread_id == uuid.UUID(thread_id),
            FileArtifact.file_path == file_path,
            FileArtifact.is_deleted == False,  # noqa: E712
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            existing.mime_type = _guess_mime_type(file_path)
            existing.updated_at = now
            await session.commit()
            return (
                f"File updated: '{file_path}' ({len(content)} bytes, id={existing.id})"
            )
        else:
            artifact = FileArtifact(
                thread_id=uuid.UUID(thread_id),
                file_path=file_path,
                content=content,
                mime_type=_guess_mime_type(file_path),
                metadata_={},
            )
            session.add(artifact)
            await session.commit()
            return (
                f"File written: '{file_path}' ({len(content)} bytes, id={artifact.id})"
            )


@tool
async def read_file(
    file_path: str,
    *,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """Read the content of a file artifact by its path.

    Use this tool to retrieve the content of a previously created file.

    Args:
        file_path: The virtual path of the file to read.
    """
    thread_id = _extract_thread_id(config)

    async with async_session_factory() as session:
        stmt = select(FileArtifact).where(
            FileArtifact.thread_id == uuid.UUID(thread_id),
            FileArtifact.file_path == file_path,
            FileArtifact.is_deleted == False,  # noqa: E712
        )
        result = await session.execute(stmt)
        artifact = result.scalar_one_or_none()

    if artifact is None:
        return f"Error: File not found at '{file_path}'."

    return (
        f"--- {file_path} ({len(artifact.content)} bytes) ---\n"
        f"{artifact.content}"
    )


@tool
async def edit_file(
    file_path: str,
    old_text: str,
    new_text: str,
    *,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """Edit a file by replacing a specific text passage with new text.

    Use this tool for targeted edits to existing files.  The ``old_text``
    must match exactly (including whitespace) and appear only once in the
    file.

    Args:
        file_path: The virtual path of the file to edit.
        old_text: The exact text to find and replace (must be unique in the file).
        new_text: The replacement text.
    """
    thread_id = _extract_thread_id(config)
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        stmt = select(FileArtifact).where(
            FileArtifact.thread_id == uuid.UUID(thread_id),
            FileArtifact.file_path == file_path,
            FileArtifact.is_deleted == False,  # noqa: E712
        )
        result = await session.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            return f"Error: File not found at '{file_path}'."

        count = artifact.content.count(old_text)
        if count == 0:
            return (
                f"Error: The specified old_text was not found in '{file_path}'."
            )
        if count > 1:
            return (
                f"Error: old_text appears {count} times in '{file_path}'. "
                "Provide a larger, unique passage to avoid ambiguity."
            )

        artifact.content = artifact.content.replace(old_text, new_text, 1)
        artifact.updated_at = now
        await session.commit()

    return f"File edited: '{file_path}' — replaced 1 occurrence ({len(new_text)} chars)."


@tool
async def delete_file(
    file_path: str,
    *,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """Delete a file artifact by its path (soft delete).

    The file will no longer appear in listings or be readable, but its
    data is retained internally.

    Args:
        file_path: The virtual path of the file to delete.
    """
    thread_id = _extract_thread_id(config)
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        stmt = (
            update(FileArtifact)
            .where(
                FileArtifact.thread_id == uuid.UUID(thread_id),
                FileArtifact.file_path == file_path,
                FileArtifact.is_deleted == False,  # noqa: E712
            )
            .values(is_deleted=True, updated_at=now)
        )
        result = await session.execute(stmt)
        await session.commit()

    if result.rowcount == 0:  # type: ignore[union-attr]
        return f"Error: File not found at '{file_path}'."

    return f"File deleted: '{file_path}'."


@tool
async def list_files(
    *,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """List all file artifacts in the current conversation thread.

    Returns a formatted listing of all active (non-deleted) files with
    their paths, sizes, and last-modified timestamps.
    """
    thread_id = _extract_thread_id(config)

    async with async_session_factory() as session:
        stmt = (
            select(FileArtifact)
            .where(
                FileArtifact.thread_id == uuid.UUID(thread_id),
                FileArtifact.is_deleted == False,  # noqa: E712
            )
            .order_by(FileArtifact.file_path)
        )
        result = await session.execute(stmt)
        artifacts = result.scalars().all()

    if not artifacts:
        return "No files found in this conversation."

    lines = [f"Found {len(artifacts)} file(s):\n"]
    for art in artifacts:
        size = len(art.content)
        modified = art.updated_at.strftime("%Y-%m-%d %H:%M:%S") if art.updated_at else "—"
        lines.append(f"  {art.file_path}  ({size} bytes, modified: {modified})")

    return "\n".join(lines)
