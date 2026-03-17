"""Tests for CompositeBackend configuration and factory integration (SYM-82).

Covers:
- CompositeBackend creation via _make_default_backend factory
- Route configuration (StateBackend default, StoreBackend for /memories/)
- Backend parameter passed through to deepagents create_deep_agent
- Native filesystem tools availability when backend is configured
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.factory import _make_default_backend, create_deep_agent

# ---------------------------------------------------------------------------
# _make_default_backend tests
# ---------------------------------------------------------------------------


class TestMakeDefaultBackend:
    """Tests for the CompositeBackend factory function."""

    def test_returns_callable(self) -> None:
        """_make_default_backend should return a callable backend factory."""
        factory = _make_default_backend()
        assert callable(factory)

    @patch("app.agents.sandbox.create_sandbox_backend", return_value=None)
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.StateBackend")
    @patch("app.agents.factory.CompositeBackend")
    def test_factory_creates_composite_backend_no_sandbox(
        self,
        mock_composite: MagicMock,
        mock_state: MagicMock,
        mock_store_backend: MagicMock,
        mock_create_sandbox: MagicMock,
    ) -> None:
        """When sandbox is disabled, the factory creates CompositeBackend with StateBackend."""
        factory = _make_default_backend()

        mock_rt = MagicMock()
        factory(mock_rt)

        # StateBackend should be created with the runtime when sandbox is disabled
        mock_state.assert_called_once_with(mock_rt)

        # StoreBackend should be created with the runtime and namespace factory
        from app.agents.factory import _user_ns_factory

        mock_store_backend.assert_called_once_with(mock_rt, namespace=_user_ns_factory)

        # CompositeBackend should be created with default=StateBackend, routes
        mock_composite.assert_called_once()
        call_kwargs = mock_composite.call_args
        assert call_kwargs.kwargs["default"] == mock_state.return_value
        assert "/memories/" in call_kwargs.kwargs["routes"]
        assert call_kwargs.kwargs["routes"]["/memories/"] == mock_store_backend.return_value

    @patch("app.agents.sandbox.create_sandbox_backend")
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.StateBackend")
    @patch("app.agents.factory.CompositeBackend")
    def test_factory_creates_composite_backend_with_sandbox(
        self,
        mock_composite: MagicMock,
        mock_state: MagicMock,
        mock_store_backend: MagicMock,
        mock_create_sandbox: MagicMock,
    ) -> None:
        """When sandbox is configured, it should replace StateBackend as the default."""
        mock_sandbox = MagicMock(name="LocalShellBackend")
        mock_create_sandbox.return_value = mock_sandbox

        factory = _make_default_backend()
        mock_rt = MagicMock()
        factory(mock_rt)

        # CompositeBackend should use the sandbox as its default backend
        call_kwargs = mock_composite.call_args
        assert call_kwargs.kwargs["default"] is mock_sandbox
        # StateBackend should NOT be called when sandbox is available
        mock_state.assert_not_called()
        # /memories/ route should still use StoreBackend
        assert "/memories/" in call_kwargs.kwargs["routes"]

    @patch("app.agents.sandbox.create_sandbox_backend", return_value=None)
    @patch("app.agents.factory.StoreBackend")
    @patch("app.agents.factory.StateBackend")
    @patch("app.agents.factory.CompositeBackend")
    def test_factory_returns_composite_instance(
        self,
        mock_composite: MagicMock,
        mock_state: MagicMock,
        mock_store_backend: MagicMock,
        mock_create_sandbox: MagicMock,
    ) -> None:
        """The factory callable should return the CompositeBackend instance."""
        factory = _make_default_backend()

        mock_rt = MagicMock()
        result = factory(mock_rt)

        assert result is mock_composite.return_value


# ---------------------------------------------------------------------------
# Factory integration tests — backend parameter
# ---------------------------------------------------------------------------


class TestFactoryBackendIntegration:
    """Tests for backend parameter in create_deep_agent."""

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_default_backend_is_passed(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """When no backend is specified, a default CompositeBackend factory is passed."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        create_deep_agent()

        call_kwargs = mock_da_create.call_args.kwargs
        assert "backend" in call_kwargs
        # The default backend should be a callable (factory function)
        assert callable(call_kwargs["backend"])

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_custom_backend_is_passed_through(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """An explicit backend parameter should be passed through unchanged."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        custom_backend = MagicMock()
        create_deep_agent(backend=custom_backend)

        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs["backend"] is custom_backend

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_backend_coexists_with_store_and_checkpointer(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """Backend, store, and checkpointer should all be passed to deepagents."""
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        mock_store = MagicMock()
        mock_checkpointer = MagicMock()
        mock_backend = MagicMock()

        create_deep_agent(
            store=mock_store,
            checkpointer=mock_checkpointer,
            backend=mock_backend,
        )

        call_kwargs = mock_da_create.call_args.kwargs
        assert call_kwargs["store"] is mock_store
        assert call_kwargs["checkpointer"] is mock_checkpointer
        assert call_kwargs["backend"] is mock_backend
