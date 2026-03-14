"""FastAPI dependency injection providers."""

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.services.thread_service import ThreadService


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, closing it when the request ends."""
    async with async_session_factory() as session:
        yield session


async def get_thread_service(
    session: AsyncSession = Depends(get_db_session),
) -> ThreadService:
    """Return a ThreadService backed by the request-scoped DB session."""
    return ThreadService(session)
