"""Tests for sandbox backend integration (SYM-90).

Covers:
- create_sandbox_backend factory with different SANDBOX_BACKEND settings
- SandboxManager per-session lifecycle (create/cleanup/cleanup_all)
- _make_default_backend integration with sandbox backend
- _parse_execute_result structured output parsing
- map_state_update execute_result SSE events
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.deepagents_adapter import _parse_execute_result, map_state_update
from app.agents.sandbox import (
    SANDBOX_LOCAL_SHELL,
    SANDBOX_NONE,
    VALID_SANDBOX_BACKENDS,
    SandboxManager,
    create_sandbox_backend,
)

# ---------------------------------------------------------------------------
# create_sandbox_backend tests
# ---------------------------------------------------------------------------


class TestCreateSandboxBackend:
    """Tests for the sandbox backend factory function."""

    @patch("app.agents.sandbox.settings")
    def test_none_backend_returns_none(self, mock_settings: MagicMock) -> None:
        """SANDBOX_BACKEND=NONE should return None (sandbox disabled)."""
        mock_settings.sandbox_backend = "NONE"
        result = create_sandbox_backend()
        assert result is None

    @patch("app.agents.sandbox.settings")
    def test_local_shell_backend_created(self, mock_settings: MagicMock) -> None:
        """SANDBOX_BACKEND=LOCAL_SHELL should create a LocalShellBackend."""
        mock_settings.sandbox_backend = "LOCAL_SHELL"
        mock_settings.sandbox_workspace_dir = "./workspace"
        mock_settings.sandbox_timeout = 120
        mock_settings.sandbox_max_output_bytes = 102400
        mock_settings.sandbox_env = {}
        mock_settings.sandbox_inherit_env = False

        mock_local_shell = MagicMock()
        mock_local_shell_cls = MagicMock(return_value=mock_local_shell)

        with patch.dict(
            "sys.modules",
            {"deepagents.backends": MagicMock(LocalShellBackend=mock_local_shell_cls)},
        ):
            result = create_sandbox_backend()

        assert result is mock_local_shell
        mock_local_shell_cls.assert_called_once_with(
            root_dir="./workspace",
            virtual_mode=True,
            timeout=120,
            max_output_bytes=102400,
            env={},
            inherit_env=False,
        )

    @patch("app.agents.sandbox.settings")
    def test_local_shell_case_insensitive(self, mock_settings: MagicMock) -> None:
        """Backend type should be case-insensitive."""
        mock_settings.sandbox_backend = "local_shell"
        mock_settings.sandbox_workspace_dir = "./workspace"
        mock_settings.sandbox_timeout = 120
        mock_settings.sandbox_max_output_bytes = 102400
        mock_settings.sandbox_env = {}
        mock_settings.sandbox_inherit_env = False

        mock_local_shell_cls = MagicMock(return_value=MagicMock())

        with patch.dict(
            "sys.modules",
            {"deepagents.backends": MagicMock(LocalShellBackend=mock_local_shell_cls)},
        ):
            result = create_sandbox_backend()

        assert result is not None

    @patch("app.agents.sandbox.settings")
    def test_modal_raises_not_implemented(self, mock_settings: MagicMock) -> None:
        """Production backends not yet integrated should raise NotImplementedError."""
        mock_settings.sandbox_backend = "MODAL"
        with pytest.raises(NotImplementedError, match="MODAL"):
            create_sandbox_backend()

    @patch("app.agents.sandbox.settings")
    def test_daytona_raises_not_implemented(self, mock_settings: MagicMock) -> None:
        """Daytona provider should raise NotImplementedError."""
        mock_settings.sandbox_backend = "DAYTONA"
        with pytest.raises(NotImplementedError, match="DAYTONA"):
            create_sandbox_backend()

    @patch("app.agents.sandbox.settings")
    def test_runloop_raises_not_implemented(self, mock_settings: MagicMock) -> None:
        """Runloop provider should raise NotImplementedError."""
        mock_settings.sandbox_backend = "RUNLOOP"
        with pytest.raises(NotImplementedError, match="RUNLOOP"):
            create_sandbox_backend()

    @patch("app.agents.sandbox.settings")
    def test_unknown_backend_raises_value_error(self, mock_settings: MagicMock) -> None:
        """Unknown backend values should raise ValueError."""
        mock_settings.sandbox_backend = "UNKNOWN_BACKEND"
        with pytest.raises(ValueError, match="UNKNOWN_BACKEND"):
            create_sandbox_backend()

    def test_valid_sandbox_backends_constant(self) -> None:
        """VALID_SANDBOX_BACKENDS should include all supported values."""
        assert SANDBOX_NONE in VALID_SANDBOX_BACKENDS
        assert SANDBOX_LOCAL_SHELL in VALID_SANDBOX_BACKENDS
        assert "MODAL" in VALID_SANDBOX_BACKENDS
        assert "DAYTONA" in VALID_SANDBOX_BACKENDS
        assert "RUNLOOP" in VALID_SANDBOX_BACKENDS


# ---------------------------------------------------------------------------
# SandboxManager tests
# ---------------------------------------------------------------------------


class TestSandboxManager:
    """Tests for SandboxManager per-session lifecycle."""

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_get_or_create_returns_backend(self, mock_create: MagicMock) -> None:
        """get_or_create should return the backend from create_sandbox_backend."""
        mock_backend = MagicMock()
        mock_create.return_value = mock_backend

        manager = SandboxManager()
        result = manager.get_or_create("thread-1")

        assert result is mock_backend
        assert manager.active_count == 1

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_get_or_create_reuses_existing_backend(self, mock_create: MagicMock) -> None:
        """Subsequent calls with the same thread_id should reuse the backend."""
        mock_backend = MagicMock()
        mock_create.return_value = mock_backend

        manager = SandboxManager()
        result1 = manager.get_or_create("thread-1")
        result2 = manager.get_or_create("thread-1")

        assert result1 is result2
        # create_sandbox_backend should only be called once
        assert mock_create.call_count == 1

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_get_or_create_none_when_disabled(self, mock_create: MagicMock) -> None:
        """When sandbox is disabled, get_or_create returns None."""
        mock_create.return_value = None

        manager = SandboxManager()
        result = manager.get_or_create("thread-1")

        assert result is None
        assert manager.active_count == 0

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_cleanup_removes_backend(self, mock_create: MagicMock) -> None:
        """cleanup should remove the backend and call teardown if available."""
        mock_backend = MagicMock(spec=[])  # no teardown method
        mock_create.return_value = mock_backend

        manager = SandboxManager()
        manager.get_or_create("thread-1")
        assert manager.active_count == 1

        asyncio.run(manager.cleanup("thread-1"))
        assert manager.active_count == 0

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_cleanup_calls_ateardown(self, mock_create: MagicMock) -> None:
        """cleanup should call ateardown() if the backend supports it."""
        mock_backend = MagicMock()
        mock_backend.ateardown = AsyncMock()
        mock_create.return_value = mock_backend

        manager = SandboxManager()
        manager.get_or_create("thread-1")

        asyncio.run(manager.cleanup("thread-1"))
        mock_backend.ateardown.assert_called_once()

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_cleanup_calls_sync_teardown(self, mock_create: MagicMock) -> None:
        """cleanup should call sync teardown() when ateardown is absent."""
        mock_backend = MagicMock(spec=["teardown"])
        mock_backend.teardown = MagicMock()
        mock_create.return_value = mock_backend

        manager = SandboxManager()
        manager.get_or_create("thread-1")

        asyncio.run(manager.cleanup("thread-1"))
        mock_backend.teardown.assert_called_once()

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_cleanup_missing_thread_is_noop(self, mock_create: MagicMock) -> None:
        """cleanup for an unknown thread_id should not raise."""
        manager = SandboxManager()
        # Should not raise even when thread is not tracked
        asyncio.run(manager.cleanup("nonexistent"))

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_cleanup_all_clears_all_sessions(self, mock_create: MagicMock) -> None:
        """cleanup_all should terminate all active sandboxes."""
        mock_create.return_value = MagicMock(spec=[])  # no teardown

        manager = SandboxManager()
        manager.get_or_create("thread-1")
        manager.get_or_create("thread-2")
        manager.get_or_create("thread-3")
        assert manager.active_count == 3

        asyncio.run(manager.cleanup_all())
        assert manager.active_count == 0

    @patch("app.agents.sandbox.create_sandbox_backend")
    def test_cleanup_continues_on_teardown_error(self, mock_create: MagicMock) -> None:
        """cleanup should not raise even if teardown() throws."""
        mock_backend = MagicMock()
        mock_backend.ateardown = AsyncMock(side_effect=RuntimeError("teardown failed"))
        mock_create.return_value = mock_backend

        manager = SandboxManager()
        manager.get_or_create("thread-1")

        # Should not raise
        asyncio.run(manager.cleanup("thread-1"))
        assert manager.active_count == 0

    def test_active_count_is_zero_initially(self) -> None:
        """A new SandboxManager should have no active sessions."""
        manager = SandboxManager()
        assert manager.active_count == 0


# ---------------------------------------------------------------------------
# _make_default_backend sandbox integration
# ---------------------------------------------------------------------------


class TestMakeDefaultBackendSandbox:
    """Tests for sandbox integration in the CompositeBackend factory."""

    @patch("app.agents.sandbox.settings")
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.CompositeBackend")
    def test_sandbox_used_as_default_when_configured(
        self,
        mock_composite: MagicMock,
        mock_store: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """When sandbox is configured, it should replace StateBackend as default."""
        mock_settings.sandbox_backend = "LOCAL_SHELL"
        mock_settings.sandbox_workspace_dir = "./workspace"
        mock_settings.sandbox_timeout = 120
        mock_settings.sandbox_max_output_bytes = 102400
        mock_settings.sandbox_env = {}
        mock_settings.sandbox_inherit_env = False

        mock_sandbox = MagicMock()
        mock_local_shell_cls = MagicMock(return_value=mock_sandbox)

        with patch.dict(
            "sys.modules",
            {"deepagents.backends": MagicMock(LocalShellBackend=mock_local_shell_cls)},
        ):
            from app.agents.factory import _make_default_backend

            factory = _make_default_backend()
            mock_rt = MagicMock()
            factory(mock_rt)

        call_kwargs = mock_composite.call_args.kwargs
        # The sandbox backend should be used as the default (not StateBackend)
        assert call_kwargs["default"] is mock_sandbox

    @patch("app.agents.sandbox.settings")
    @patch("app.agents.factory.StateBackend")
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.CompositeBackend")
    def test_state_backend_used_when_sandbox_disabled(
        self,
        mock_composite: MagicMock,
        mock_store: MagicMock,
        mock_state: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """When sandbox is disabled (NONE), StateBackend should be used."""
        mock_settings.sandbox_backend = "NONE"

        from app.agents.factory import _make_default_backend

        factory = _make_default_backend()
        mock_rt = MagicMock()
        factory(mock_rt)

        call_kwargs = mock_composite.call_args.kwargs
        assert call_kwargs["default"] is mock_state.return_value

    @patch("app.agents.sandbox.settings")
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.CompositeBackend")
    @patch("app.agents.factory.sandbox_manager")
    def test_sandbox_manager_used_when_thread_id_present(
        self,
        mock_manager: MagicMock,
        mock_composite: MagicMock,
        mock_store: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """When thread_id is in the runtime config, sandbox_manager.get_or_create is used."""
        mock_settings.sandbox_backend = "LOCAL_SHELL"
        mock_sandbox = MagicMock()
        mock_manager.get_or_create.return_value = mock_sandbox

        from app.agents.factory import _make_default_backend

        factory = _make_default_backend()
        mock_rt = MagicMock()
        mock_rt.config = {"configurable": {"thread_id": "test-thread-123"}}
        factory(mock_rt)

        mock_manager.get_or_create.assert_called_once_with("test-thread-123")
        call_kwargs = mock_composite.call_args.kwargs
        assert call_kwargs["default"] is mock_sandbox

    @patch("app.agents.sandbox.settings")
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.CompositeBackend")
    @patch("app.agents.factory.create_sandbox_backend")
    def test_create_sandbox_backend_used_when_no_thread_id(
        self,
        mock_create: MagicMock,
        mock_composite: MagicMock,
        mock_store: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """When no thread_id is available, create_sandbox_backend is called directly."""
        mock_settings.sandbox_backend = "LOCAL_SHELL"
        mock_sandbox = MagicMock()
        mock_create.return_value = mock_sandbox

        from app.agents.factory import _make_default_backend

        factory = _make_default_backend()
        # MagicMock config — isinstance check returns False → no thread_id path
        mock_rt = MagicMock()
        factory(mock_rt)

        mock_create.assert_called_once()
        call_kwargs = mock_composite.call_args.kwargs
        assert call_kwargs["default"] is mock_sandbox


# ---------------------------------------------------------------------------
# _parse_execute_result tests
# ---------------------------------------------------------------------------


class TestParseExecuteResult:
    """Tests for execute tool output parsing."""

    def test_parses_json_output(self) -> None:
        """JSON-formatted execute results should be parsed correctly."""
        content = '{"stdout": "hello world", "stderr": "", "exit_code": 0}'
        result = _parse_execute_result(content)
        assert result["stdout"] == "hello world"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0

    def test_parses_json_with_returncode(self) -> None:
        """JSON with 'returncode' key (alternate name) should be handled."""
        content = '{"stdout": "output", "stderr": "warning", "returncode": 1}'
        result = _parse_execute_result(content)
        assert result["stdout"] == "output"
        assert result["stderr"] == "warning"
        assert result["exit_code"] == 1

    def test_parses_text_exit_code(self) -> None:
        """Plain text with 'Exit code: N' should extract the exit code."""
        content = "Exit code: 0\nstdout:\nhello\nstderr:\n"
        result = _parse_execute_result(content)
        assert result["exit_code"] == 0

    def test_parses_nonzero_exit_code(self) -> None:
        """Non-zero exit codes should be captured."""
        content = "Exit code: 1\nstdout:\n\nstderr:\ncommand not found"
        result = _parse_execute_result(content)
        assert result["exit_code"] == 1

    def test_parses_negative_exit_code(self) -> None:
        """Negative exit codes (e.g. -1 for timeout) should be captured."""
        content = "Exit code: -1\nstdout:\n\nstderr:\ntimeout"
        result = _parse_execute_result(content)
        assert result["exit_code"] == -1

    def test_fallback_raw_content_as_stdout(self) -> None:
        """Unstructured content should be returned as stdout."""
        content = "some plain output"
        result = _parse_execute_result(content)
        assert result["stdout"] == "some plain output"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0

    def test_empty_content(self) -> None:
        """Empty content should return empty stdout/stderr and exit_code 0."""
        result = _parse_execute_result("")
        assert result["stdout"] == ""
        assert result["stderr"] == ""
        assert result["exit_code"] == 0

    def test_json_with_nested_data(self) -> None:
        """JSON with extra fields should still extract stdout/stderr/exit_code."""
        content = '{"stdout": "result", "stderr": "", "exit_code": 0, "extra": "ignored"}'
        result = _parse_execute_result(content)
        assert result["stdout"] == "result"
        assert result["exit_code"] == 0


# ---------------------------------------------------------------------------
# map_state_update execute_result event tests
# ---------------------------------------------------------------------------


class TestMapStateUpdateExecuteResult:
    """Tests for execute_result SSE events emitted from map_state_update."""

    def _make_tool_message(self, content: str, name: str, tool_call_id: str) -> Any:
        from langchain_core.messages import ToolMessage

        return ToolMessage(content=content, name=name, tool_call_id=tool_call_id)

    def test_execute_tool_emits_execute_result_event(self) -> None:
        """execute tool should emit an execute_result SSE event."""
        msg = self._make_tool_message(
            content='{"stdout": "hello", "stderr": "", "exit_code": 0}',
            name="execute",
            tool_call_id="run_1",
        )
        update = {"tools": {"messages": [msg]}}
        events = map_state_update(update)

        event_types = [e.event for e in events]
        assert "execute_result" in event_types

    def test_execute_result_has_structured_fields(self) -> None:
        """execute_result event should contain stdout, stderr, and exit_code."""
        msg = self._make_tool_message(
            content='{"stdout": "hello\\nworld", "stderr": "warning", "exit_code": 2}',
            name="execute",
            tool_call_id="run_1",
        )
        update = {"tools": {"messages": [msg]}}
        events = map_state_update(update)

        execute_events = [e for e in events if e.event == "execute_result"]
        assert len(execute_events) == 1
        data = execute_events[0].data
        assert data["stdout"] == "hello\nworld"
        assert data["stderr"] == "warning"
        assert data["exit_code"] == 2

    def test_execute_result_run_id_matches(self) -> None:
        """execute_result run_id should match the tool_call_id."""
        msg = self._make_tool_message(
            content='{"stdout": "", "stderr": "", "exit_code": 0}',
            name="execute",
            tool_call_id="call_abc123",
        )
        update = {"tools": {"messages": [msg]}}
        events = map_state_update(update)

        execute_events = [e for e in events if e.event == "execute_result"]
        assert execute_events[0].data["run_id"] == "call_abc123"

    def test_execute_also_emits_file_event_and_tool_result(self) -> None:
        """execute tool should still emit file_event and tool_result alongside execute_result."""
        msg = self._make_tool_message(
            content='{"stdout": "output", "stderr": "", "exit_code": 0}',
            name="execute",
            tool_call_id="run_2",
        )
        update = {"tools": {"messages": [msg]}}
        events = map_state_update(update)

        event_types = [e.event for e in events]
        assert "file_event" in event_types
        assert "tool_result" in event_types
        assert "execute_result" in event_types

    def test_non_execute_tool_does_not_emit_execute_result(self) -> None:
        """Non-execute tools should NOT emit execute_result events."""
        msg = self._make_tool_message(
            content="file contents",
            name="read_file",
            tool_call_id="run_3",
        )
        update = {"tools": {"messages": [msg]}}
        events = map_state_update(update)

        event_types = [e.event for e in events]
        assert "execute_result" not in event_types
        assert "file_event" in event_types
        assert "tool_result" in event_types

    def test_execute_with_nonzero_exit_code(self) -> None:
        """execute_result should capture non-zero exit codes."""
        msg = self._make_tool_message(
            content='{"stdout": "", "stderr": "error: file not found", "exit_code": 127}',
            name="execute",
            tool_call_id="run_4",
        )
        update = {"tools": {"messages": [msg]}}
        events = map_state_update(update)

        execute_events = [e for e in events if e.event == "execute_result"]
        assert execute_events[0].data["exit_code"] == 127
        assert execute_events[0].data["stderr"] == "error: file not found"
