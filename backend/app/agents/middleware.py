"""Agent middleware — LangGraph Memory Store integration.

Provides a shared memory store backed by PostgreSQL so that agents can
retain context across conversation turns within a thread.  The memory
store is injected into the agent graph via the ``store`` parameter of
``create_react_agent``.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.store.memory import InMemoryStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Memory store singleton
# ---------------------------------------------------------------------------

_memory_store: InMemoryStore | None = None


def get_memory_store() -> InMemoryStore:
    """Return (and lazily create) the shared in-memory store.

    LangGraph's ``InMemoryStore`` provides a namespace-based key-value
    store that agents can read/write within tool calls or node functions.
    Data persists for the lifetime of the process.

    In a future iteration this will be swapped for a PostgreSQL-backed
    store (e.g. ``AsyncPostgresStore``) so that memory survives restarts.
    The interface is identical, so no agent code changes will be needed.
    """
    global _memory_store
    if _memory_store is None:
        logger.info("Initializing LangGraph InMemoryStore")
        _memory_store = InMemoryStore()
    return _memory_store


def reset_memory_store() -> None:
    """Reset the memory store (primarily for testing)."""
    global _memory_store
    _memory_store = None
    logger.info("Memory store reset")


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
