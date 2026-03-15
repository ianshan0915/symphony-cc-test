"""Agent middleware — LangGraph Memory Store & Checkpointer integration.

Provides shared, production-grade persistence backends for LangGraph agents:

* **Store** — ``AsyncPostgresStore`` for cross-turn memory (namespace-scoped
  key-value data that survives process restarts).  Falls back to
  ``InMemoryStore`` when the Postgres package is unavailable or setup fails.

* **Checkpointer** — ``AsyncPostgresSaver`` for checkpoint persistence so
  thread state is durable across restarts.  Falls back to ``MemorySaver``.

Both backends are initialised once at application startup via
:func:`setup_persistent_backends` and torn down via
:func:`teardown_persistent_backends`.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------

_memory_store: Any | None = None
_checkpointer: Any | None = None
_checkpointer_pool: Any | None = None

# Track whether we are using persistent (Postgres) backends
_using_persistent_store: bool = False
_using_persistent_checkpointer: bool = False


# ---------------------------------------------------------------------------
# Async setup / teardown (called from app lifespan)
# ---------------------------------------------------------------------------


async def setup_persistent_backends() -> None:
    """Initialise PostgreSQL-backed store and checkpointer.

    Called once during application startup.  On import or connection
    failure the function silently falls back to in-memory backends so
    the application can still run (useful in CI / local-dev without PG).
    """
    global _memory_store, _checkpointer, _checkpointer_pool
    global _using_persistent_store, _using_persistent_checkpointer

    conn_string = settings.database_url_psycopg

    # --- Store ---
    try:
        from langgraph.store.postgres import AsyncPostgresStore

        store = AsyncPostgresStore.from_conn_string(conn_string)
        # __aenter__ opens the connection pool
        _memory_store = await store.__aenter__()
        await _memory_store.setup()
        _using_persistent_store = True
        logger.info("Persistent AsyncPostgresStore initialised")
    except Exception:
        logger.warning(
            "Failed to initialise AsyncPostgresStore — falling back to InMemoryStore",
            exc_info=True,
        )
        _memory_store = InMemoryStore()
        _using_persistent_store = False

    # --- Checkpointer ---
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection
        from psycopg_pool import AsyncConnectionPool

        _checkpointer_pool = AsyncConnectionPool(
            conn_string,
            min_size=1,
            max_size=settings.db_pool_size,
            open=False,
        )
        await _checkpointer_pool.open()
        _checkpointer = AsyncPostgresSaver(_checkpointer_pool)

        # Run setup() with a dedicated autocommit connection because the
        # checkpoint migration contains CREATE INDEX CONCURRENTLY which
        # PostgreSQL forbids inside a transaction block.  See SYM-57.
        async with await AsyncConnection.connect(conn_string, autocommit=True) as setup_conn:
            setup_saver = AsyncPostgresSaver(setup_conn)
            await setup_saver.setup()
        _using_persistent_checkpointer = True
        logger.info("Persistent AsyncPostgresSaver initialised (pooled)")
    except Exception:
        logger.warning(
            "Failed to initialise AsyncPostgresSaver — falling back to MemorySaver",
            exc_info=True,
        )
        _checkpointer = MemorySaver()
        _using_persistent_checkpointer = False


async def teardown_persistent_backends() -> None:
    """Gracefully close persistent backends (called at shutdown)."""
    global _memory_store, _checkpointer, _checkpointer_pool

    if _using_persistent_store and _memory_store is not None:
        try:
            await _memory_store.__aexit__(None, None, None)
            logger.info("AsyncPostgresStore closed")
        except Exception:
            logger.warning("Error closing AsyncPostgresStore", exc_info=True)

    if _using_persistent_checkpointer and _checkpointer_pool is not None:
        try:
            await _checkpointer_pool.close()
            logger.info("AsyncPostgresSaver connection pool closed")
        except Exception:
            logger.warning("Error closing AsyncPostgresSaver pool", exc_info=True)

    _memory_store = None
    _checkpointer = None
    _checkpointer_pool = None


# ---------------------------------------------------------------------------
# Accessors (used by factory / agent service)
# ---------------------------------------------------------------------------


def get_memory_store() -> Any:
    """Return the shared memory store (Postgres or in-memory).

    Lazily creates an ``InMemoryStore`` if persistent backends have not
    been set up yet (e.g. during unit tests).
    """
    global _memory_store
    if _memory_store is None:
        logger.info("Initialising fallback InMemoryStore (no persistent backend)")
        _memory_store = InMemoryStore()
    return _memory_store


def get_checkpointer() -> Any:
    """Return the shared checkpointer (Postgres or in-memory).

    Lazily creates a ``MemorySaver`` if persistent backends have not been
    set up yet (e.g. during unit tests).
    """
    global _checkpointer
    if _checkpointer is None:
        logger.info("Initialising fallback MemorySaver (no persistent backend)")
        _checkpointer = MemorySaver()
    return _checkpointer


def reset_memory_store() -> None:
    """Reset the memory store (primarily for testing)."""
    global _memory_store, _using_persistent_store
    _memory_store = None
    _using_persistent_store = False
    logger.info("Memory store reset")


def reset_checkpointer() -> None:
    """Reset the checkpointer (primarily for testing)."""
    global _checkpointer, _checkpointer_pool, _using_persistent_checkpointer
    _checkpointer = None
    _checkpointer_pool = None
    _using_persistent_checkpointer = False
    logger.info("Checkpointer reset")


# ---------------------------------------------------------------------------
# Middleware helpers
# ---------------------------------------------------------------------------


def build_agent_kwargs(
    *,
    thread_id: str | None = None,
    user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build keyword arguments for agent invocation with memory support.

    Returns a dict suitable for passing as ``config`` to the compiled
    agent's ``.ainvoke()`` or ``.astream_events()`` methods.

    Parameters
    ----------
    thread_id:
        Conversation thread identifier for checkpointing.
    user_id:
        User identifier for memory namespacing.
    extra:
        Additional configuration to merge.

    Returns
    -------
    dict
        Configuration dict with ``configurable`` and ``store`` keys.
    """
    configurable: dict[str, Any] = {}
    if thread_id:
        configurable["thread_id"] = thread_id
    if user_id:
        configurable["user_id"] = user_id

    config: dict[str, Any] = {"configurable": configurable}

    if extra:
        config.update(extra)

    return config
