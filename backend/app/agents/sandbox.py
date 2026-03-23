"""Sandbox backend factory and per-session lifecycle management.

Provides the ``execute`` tool for running shell commands in isolated
environments.  The backend type is selected via the ``SANDBOX_BACKEND``
environment variable:

* ``LOCAL_SHELL`` — :class:`~deepagents.backends.LocalShellBackend` for
  local development.  Commands run on the host machine inside
  ``SANDBOX_WORKSPACE_DIR`` with ``virtual_mode=True`` so that file paths
  are interpreted relative to a virtual root (compatible with
  :class:`~deepagents.backends.CompositeBackend` routing).
* ``MODAL`` / ``DAYTONA`` / ``RUNLOOP`` — cloud sandbox providers.
  These are declared as supported backend types but require provider-specific
  integration (raise ``NotImplementedError`` until implemented).
* ``NONE`` — sandbox execution disabled; the ``execute`` tool is not
  available.

Sandbox lifecycle
-----------------
:class:`SandboxManager` tracks one sandbox backend per session (thread).
For :class:`~deepagents.backends.LocalShellBackend` the lifecycle is
lightweight (a new instance per session is fine).  Production backends
should override :meth:`SandboxManager.cleanup` to call the provider API
and terminate the sandbox.

Usage::

    # In factory.py — integrate with CompositeBackend
    from app.agents.sandbox import create_sandbox_backend
    sandbox = create_sandbox_backend()  # LocalShellBackend or None

    # In agent_service.py — per-session lifecycle
    from app.agents.sandbox import sandbox_manager
    backend = sandbox_manager.get_or_create(thread_id)
    ...
    await sandbox_manager.cleanup(thread_id)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported sandbox backend type constants
# ---------------------------------------------------------------------------

#: Disable code execution entirely.
SANDBOX_NONE = "NONE"

#: LocalShellBackend — local development only, no true isolation.
SANDBOX_LOCAL_SHELL = "LOCAL_SHELL"

#: Cloud sandbox providers (require provider SDK integration).
SANDBOX_MODAL = "MODAL"
SANDBOX_DAYTONA = "DAYTONA"
SANDBOX_RUNLOOP = "RUNLOOP"

#: All valid SANDBOX_BACKEND values.
VALID_SANDBOX_BACKENDS: frozenset[str] = frozenset(
    {SANDBOX_NONE, SANDBOX_LOCAL_SHELL, SANDBOX_MODAL, SANDBOX_DAYTONA, SANDBOX_RUNLOOP}
)


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------


def create_sandbox_backend() -> Any | None:
    """Create a sandbox backend instance based on application configuration.

    Returns
    -------
    Any | None
        A backend instance implementing
        :class:`~deepagents.backends.SandboxBackendProtocol`, or ``None``
        when sandbox execution is disabled (``SANDBOX_BACKEND=NONE``).

    Raises
    ------
    ValueError
        If ``SANDBOX_BACKEND`` is set to an unrecognised value.
    NotImplementedError
        If ``SANDBOX_BACKEND`` names a provider that is not yet integrated.
    ImportError
        If the ``deepagents`` package is not installed.
    """
    backend_type = settings.sandbox_backend.upper().strip()

    if backend_type == SANDBOX_NONE:
        logger.debug("Sandbox backend disabled (SANDBOX_BACKEND=NONE)")
        return None

    if backend_type == SANDBOX_LOCAL_SHELL:
        try:
            from deepagents.backends import LocalShellBackend
        except ImportError as exc:
            raise ImportError(
                "deepagents package is required for LocalShellBackend. "
                "Install it with: pip install deepagents"
            ) from exc

        # Ensure the workspace directory exists
        os.makedirs(settings.sandbox_workspace_dir, exist_ok=True)

        backend = LocalShellBackend(
            root_dir=settings.sandbox_workspace_dir,
            # virtual_mode=True tells LocalShellBackend to expose a
            # *virtual* root for the CompositeBackend routing protocol.
            # This means deepagents treats this backend as a virtual-path
            # provider, so path-prefix routing (e.g. /memories/ → StoreBackend)
            # works correctly without the LocalShellBackend intercepting those
            # paths and writing them to disk.
            #
            # Crucially, virtual_mode affects only the *file-operation* API
            # (read_file, write_file, etc.) path routing within the backend
            # protocol — it does NOT intercept or sandbox the underlying
            # subprocess launched by the ``execute`` tool.  Shell commands
            # always run as real processes with access to the host filesystem
            # under ``root_dir``.  This is intentional for local development:
            # code written via write_file and then executed can be read/run
            # using real paths.
            virtual_mode=True,
            timeout=settings.sandbox_timeout,
            max_output_bytes=settings.sandbox_max_output_bytes,
            env=settings.sandbox_env or {},
            inherit_env=settings.sandbox_inherit_env,
        )
        logger.info(
            "LocalShellBackend created: root_dir=%s, timeout=%ds, "
            "max_output_bytes=%d, inherit_env=%s",
            settings.sandbox_workspace_dir,
            settings.sandbox_timeout,
            settings.sandbox_max_output_bytes,
            settings.sandbox_inherit_env,
        )
        return backend

    if backend_type in (SANDBOX_MODAL, SANDBOX_DAYTONA, SANDBOX_RUNLOOP):
        raise NotImplementedError(
            f"Sandbox backend '{backend_type}' is declared but not yet integrated. "
            "Implement the provider-specific backend by subclassing "
            "deepagents.backends.BaseSandbox and register it here."
        )

    raise ValueError(
        f"Unknown SANDBOX_BACKEND value: '{settings.sandbox_backend}'. "
        f"Valid values: {', '.join(sorted(VALID_SANDBOX_BACKENDS))}"
    )


# ---------------------------------------------------------------------------
# Lifecycle manager
# ---------------------------------------------------------------------------


class SandboxManager:
    """Per-session sandbox lifecycle manager.

    Tracks one sandbox backend per thread (session) so that long-running
    production sandboxes can be reused across turns and properly cleaned up
    when the session ends.

    For :class:`~deepagents.backends.LocalShellBackend` (local development),
    each session gets its own backend instance so concurrent threads don't
    share mutable state.  Production sandbox providers should maintain a
    persistent instance per thread so the same container is reused across
    multiple turns.

    Usage::

        manager = SandboxManager()

        # At session start (or first tool use)
        backend = manager.get_or_create("thread-abc")

        # At session end
        await manager.cleanup("thread-abc")

        # At application shutdown
        await manager.cleanup_all()

    Thread safety
    -------------
    :meth:`get_or_create` is intentionally synchronous (called from the
    deepagents backend factory which is sync).  The dict read-and-update is
    safe on CPython because the GIL makes both operations atomic.  A missing
    thread_id can cause two concurrent calls to both create a backend — the
    second write wins and the first backend is abandoned.  For
    :class:`~deepagents.backends.LocalShellBackend` this is harmless because
    the backend is lightweight.  Cloud sandbox providers that require
    explicit creation (e.g. container spin-up) should refactor to use an
    async lock before wiring in.
    """

    def __init__(self) -> None:
        self._sandboxes: dict[str, Any] = {}
        # No asyncio.Lock here: get_or_create is sync (called from a sync
        # backend factory).  CPython GIL protects the dict update.  See the
        # class docstring "Thread safety" note above.

    def get_or_create(self, thread_id: str) -> Any | None:
        """Return the sandbox backend for a session, creating it if absent.

        Parameters
        ----------
        thread_id:
            Unique session / thread identifier.

        Returns
        -------
        Any | None
            A backend implementing
            :class:`~deepagents.backends.SandboxBackendProtocol`, or
            ``None`` if sandbox execution is disabled.
        """
        if thread_id not in self._sandboxes:
            backend = create_sandbox_backend()
            if backend is not None:
                self._sandboxes[thread_id] = backend
                logger.debug("Sandbox backend created for thread_id=%s", thread_id)
            return backend
        return self._sandboxes.get(thread_id)

    async def cleanup(self, thread_id: str) -> None:
        """Terminate and remove the sandbox for a session.

        For :class:`~deepagents.backends.LocalShellBackend`, cleanup is a
        no-op (the backend is stateless).  For production providers, override
        this to call the provider API and release sandbox resources.

        Parameters
        ----------
        thread_id:
            Session identifier whose sandbox should be terminated.
        """
        backend = self._sandboxes.pop(thread_id, None)
        if backend is None:
            return

        try:
            if hasattr(backend, "ateardown"):
                await backend.ateardown()
            elif hasattr(backend, "teardown"):
                backend.teardown()
            logger.debug("Sandbox cleaned up for thread_id=%s", thread_id)
        except Exception:
            logger.exception(
                "Error cleaning up sandbox for thread_id=%s; continuing shutdown",
                thread_id,
            )

    async def cleanup_all(self) -> None:
        """Terminate all active sandboxes.  Call at application shutdown."""
        thread_ids = list(self._sandboxes.keys())
        for thread_id in thread_ids:
            await self.cleanup(thread_id)
        if thread_ids:
            logger.info("All sandboxes cleaned up (%d sessions)", len(thread_ids))

    @property
    def active_count(self) -> int:
        """Number of currently active sandbox sessions."""
        return len(self._sandboxes)


#: Application-wide singleton :class:`SandboxManager`.
sandbox_manager = SandboxManager()
