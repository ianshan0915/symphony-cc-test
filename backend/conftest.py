"""Root conftest — register stub ``deepagents`` module before any app imports.

The ``deepagents`` package requires Python ≥ 3.11 and may not be
installable in every CI / local environment.  This conftest injects
lightweight stubs into ``sys.modules`` so that the top-level imports in
``app.agents.factory`` succeed and tests can patch the symbols normally.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

# Only install stubs if deepagents is not already available.
if "deepagents" not in sys.modules:
    # --- deepagents (top-level) ---
    _da = types.ModuleType("deepagents")
    _da.create_deep_agent = MagicMock(name="create_deep_agent")  # type: ignore[attr-defined]
    sys.modules["deepagents"] = _da

    # --- deepagents.backends ---
    _backends = types.ModuleType("deepagents.backends")
    _backends.BackendContext = MagicMock(name="BackendContext")  # type: ignore[attr-defined]
    _backends.CompositeBackend = MagicMock(name="CompositeBackend")  # type: ignore[attr-defined]
    _backends.StateBackend = MagicMock(name="StateBackend")  # type: ignore[attr-defined]
    _backends.StoreBackend = MagicMock(name="StoreBackend")  # type: ignore[attr-defined]
    sys.modules["deepagents.backends"] = _backends
