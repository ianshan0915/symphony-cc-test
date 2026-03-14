"""Thread service — business logic for thread CRUD operations."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.thread import Thread, ThreadCreate, ThreadUpdate


class ThreadService:
    """Encapsulates all thread-related database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ThreadCreate) -> Thread:
        """Create a new conversation thread."""
        thread = Thread(
            title=data.title,
            assistant_id=data.assistant_id,
            metadata_=data.metadata,
        )
        self._session.add(thread)
        await self._session.commit()
        await self._session.refresh(thread)
        return thread

    async def list(self, *, offset: int = 0, limit: int = 20) -> tuple[list[Thread], int]:
        """Return paginated list of non-deleted threads (newest first)."""
        # Count query
        count_stmt = select(func.count()).select_from(Thread).where(Thread.is_deleted.is_(False))
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Data query
        stmt = (
            select(Thread)
            .where(Thread.is_deleted.is_(False))
            .order_by(Thread.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        threads = list(result.scalars().all())
        return threads, total

    async def get(self, thread_id: uuid.UUID) -> Thread | None:
        """Get a single thread by ID with its messages (eager-loaded)."""
        stmt = (
            select(Thread)
            .where(Thread.id == thread_id, Thread.is_deleted.is_(False))
            .options(selectinload(Thread.messages))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, thread_id: uuid.UUID, data: ThreadUpdate) -> Thread | None:
        """Update thread fields. Returns None if not found."""
        thread = await self.get(thread_id)
        if thread is None:
            return None

        if data.title is not None:
            thread.title = data.title
        if data.metadata is not None:
            thread.metadata_ = data.metadata

        await self._session.commit()
        await self._session.refresh(thread)
        return thread

    async def delete(self, thread_id: uuid.UUID) -> bool:
        """Soft-delete a thread. Returns False if not found."""
        stmt = select(Thread).where(Thread.id == thread_id, Thread.is_deleted.is_(False))
        result = await self._session.execute(stmt)
        thread = result.scalar_one_or_none()
        if thread is None:
            return False

        thread.is_deleted = True
        await self._session.commit()
        return True
