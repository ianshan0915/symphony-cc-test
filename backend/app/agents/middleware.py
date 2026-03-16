"""Agent middleware — persistence backends for deep agents.

Provides shared, production-grade persistence backends consumed by
``deepagents.create_deep_agent()`` via its ``checkpointer`` and ``store``
parameters:

* **Store** — ``AsyncPostgresStore`` for cross-turn memory (namespace-scoped
  key-value data that survives process restarts).  Falls back to
  ``InMemoryStore`` when the Postgres package is unavailable or setup fails.

* **Checkpointer** — ``AsyncPostgresSaver`` for checkpoint persistence so
  thread state is durable across restarts.  Falls back to ``MemorySaver``.

Both backends are initialised once at application startup via
:func:`setup_persistent_backends` and torn down via
:func:`teardown_persistent_backends`.

AGENTS.md — persistent memory file
-----------------------------------
A global ``/memories/AGENTS.md`` file is seeded into the store on first run.
Deep agents load this file at conversation start (via
``memory=["/memories/AGENTS.md"]``), and can update it with learned
preferences, project context, and conventions so the information persists
across threads.

The path ``/memories/AGENTS.md`` is intentional: the ``CompositeBackend`` in
``factory.py`` routes all ``/memories/`` paths to ``StoreBackend``, which
reads/writes files as LangGraph store items using the file path as the key
and the namespace ``("filesystem",)`` (deepagents default).  Seeding and the
API helpers must use the same namespace and key format so that deepagents can
find and update the file.

The ``GET /memory`` and ``PUT /memory`` API endpoints expose this file for
human editing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AGENTS.md persistent memory constants
# ---------------------------------------------------------------------------

#: LangGraph store namespace used by ``StoreBackend`` (deepagents default).
#:
#: ``StoreBackend`` resolves its namespace via ``_get_namespace_legacy()`` which
#: defaults to ``("filesystem",)`` when no ``assistant_id`` is present in the
#: request config.  Our seed/get/set helpers must use this same namespace so
#: that deepagents can find the seeded file at runtime.
AGENTS_MD_NAMESPACE: tuple[str, ...] = ("filesystem",)

#: File path used as the store key for AGENTS.md.
#:
#: The path lives under ``/memories/`` so the ``CompositeBackend`` routes it
#: to ``StoreBackend`` (persistent cross-thread storage) rather than the
#: ephemeral ``StateBackend``.
AGENTS_MD_KEY: str = "/memories/AGENTS.md"

#: Default initial content seeded into the store when it is first created.
DEFAULT_AGENTS_MD_CONTENT: str = """\
# Symphony Agent Memory

This file provides persistent context loaded by agents at the start of every
conversation.  Agents can update it to remember preferences, project
conventions, and learned knowledge across threads.

## Project Conventions

<!-- Add project-specific conventions here -->

## User Preferences

<!-- Add user preferences here (e.g. communication style, output format) -->

## Learned Context

<!-- Agents append discoveries here automatically -->
"""

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

    # Seed the default AGENTS.md content if it does not exist yet
    await _seed_agents_md_if_missing()

    # --- Checkpointer ---
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection
        from psycopg.rows import dict_row
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
        async with await AsyncConnection.connect(
            conn_string, autocommit=True, row_factory=dict_row
        ) as setup_conn:
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
# AGENTS.md memory helpers
# ---------------------------------------------------------------------------


def _make_file_data(content: str, *, created_at: str | None = None) -> dict[str, Any]:
    """Build a store value dict in the format expected by ``StoreBackend``.

    ``StoreBackend`` stores files as ``{"content": list[str], "created_at": str,
    "modified_at": str}`` where ``content`` is the file text split on newlines.
    Our seed/get/set helpers must produce and consume values in this same format.

    Parameters
    ----------
    content:
        Full file text.
    created_at:
        ISO-formatted creation timestamp.  Defaults to *now* when ``None``.
    """
    now = datetime.now(UTC).isoformat()
    return {
        "content": content.split("\n"),
        "created_at": created_at or now,
        "modified_at": now,
    }


async def _seed_agents_md_if_missing() -> None:
    """Seed the default AGENTS.md content into the store if absent.

    Called once during startup after the store is initialised.  A no-op
    when content already exists so user edits are never overwritten.
    """
    store = get_memory_store()
    try:
        existing = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)
        if existing is None:
            await store.aput(
                AGENTS_MD_NAMESPACE,
                AGENTS_MD_KEY,
                _make_file_data(DEFAULT_AGENTS_MD_CONTENT),
            )
            logger.info("Seeded default AGENTS.md content into store")
        else:
            logger.debug("AGENTS.md already present in store — skipping seed")
    except Exception:
        logger.warning("Failed to seed AGENTS.md into store", exc_info=True)


async def get_agents_md() -> str:
    """Return the current AGENTS.md content from the store.

    Falls back to :data:`DEFAULT_AGENTS_MD_CONTENT` if the key is missing
    or unreadable (e.g. store not yet initialised).

    The value stored by ``_seed_agents_md_if_missing`` and ``set_agents_md``
    uses the ``StoreBackend`` file format: ``{"content": list[str], ...}``.
    Lines are joined with ``"\\n"`` to reconstruct the original text.
    """
    store = get_memory_store()
    try:
        item = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)
        if item is not None:
            value = item.value if hasattr(item, "value") else item
            raw = value.get("content", DEFAULT_AGENTS_MD_CONTENT)
            # StoreBackend stores content as a list of lines
            if isinstance(raw, list):
                return "\n".join(raw)
            return str(raw)
    except Exception:
        logger.warning("Failed to read AGENTS.md from store", exc_info=True)
    return DEFAULT_AGENTS_MD_CONTENT


async def set_agents_md(content: str) -> None:
    """Write new AGENTS.md *content* to the store.

    Preserves the original ``created_at`` timestamp if the file already
    exists; otherwise creates a fresh timestamp.  The value is written in
    ``StoreBackend`` file format so that deepagents can read it directly.

    Parameters
    ----------
    content:
        The full Markdown text to persist as the new AGENTS.md.
    """
    store = get_memory_store()
    # Preserve creation timestamp from the existing item when available
    created_at: str | None = None
    try:
        existing = await store.aget(AGENTS_MD_NAMESPACE, AGENTS_MD_KEY)
        if existing is not None:
            value = existing.value if hasattr(existing, "value") else existing
            created_at = value.get("created_at")
    except Exception:
        logger.debug("Could not read existing AGENTS.md created_at", exc_info=True)

    await store.aput(
        AGENTS_MD_NAMESPACE,
        AGENTS_MD_KEY,
        _make_file_data(content, created_at=created_at),
    )
    logger.info("AGENTS.md updated in store (%d chars)", len(content))


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
    agent's ``.ainvoke()`` or ``.astream()`` methods.

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
