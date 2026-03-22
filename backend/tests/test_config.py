"""Tests for application configuration (backend/app/config.py).

Regression tests for SYM-55: ensure LangSmith env vars are accepted by the
Settings model without raising ``ValidationError``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError  # noqa: F401 — referenced in docstrings


def test_settings_accepts_langsmith_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should not reject LANGSMITH_TRACING or LANGSMITH_ENDPOINT."""
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    # Avoid reading a real .env file during tests
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")

    from app.config import Settings

    # Must not raise pydantic_core.ValidationError
    s = Settings()
    assert s.langsmith_tracing is True
    assert s.langsmith_endpoint == "https://api.smith.langchain.com"


def test_settings_langsmith_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """LangSmith fields should have sensible defaults when env vars are absent."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)

    from app.config import Settings

    # Disable .env file loading so the test checks true defaults rather than
    # values sourced from the on-disk .env file (fixes SYM-61).
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.langsmith_tracing is False
    assert s.langsmith_endpoint == ""
