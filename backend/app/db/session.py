"""Async SQLAlchemy engine and session factory.

Connection pool is tuned for production workloads:
- ``pool_size`` — number of persistent connections kept open.
- ``max_overflow`` — additional connections allowed under burst load.
- ``pool_recycle`` — max lifetime (seconds) of a connection before it is
  transparently replaced, preventing stale-connection errors behind
  PgBouncer / cloud proxies.
- ``pool_timeout`` — seconds to wait for a free connection before raising.
- ``pool_pre_ping`` — test each connection with a lightweight ``SELECT 1``
  before handing it to a caller, so broken connections are discarded.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
