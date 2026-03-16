"""Tests for the human-in-the-loop approval flow using native interrupt_on (SYM-83)."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.services.agent_service import (
    INTERRUPT_ON,
    TOOLS_REQUIRING_APPROVAL,
    AgentService,
    SSEEvent,
    _PendingInterrupt,
)

# ---------------------------------------------------------------------------
# _PendingInterrupt unit tests
# ---------------------------------------------------------------------------


class TestPendingInterrupt:
    """Unit tests for the _PendingInterrupt internal class."""

    def test_default_values(self) -> None:
        pi = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="test-id",
            interrupt_data={
                "tool_name": "web_search",
                "tool_args": {"query": "test"},
                "run_id": "run-1",
            },
        )
        assert pi.decision is None
        assert not pi.decision_event.is_set()
        assert pi.interrupt_data["tool_name"] == "web_search"

    def test_decision_event_signalling(self) -> None:
        pi = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="test-id",
            interrupt_data={},
        )
        assert not pi.decision_event.is_set()
        pi.decision = {"type": "approve"}
        pi.decision_event.set()
        assert pi.decision_event.is_set()


# ---------------------------------------------------------------------------
# AgentService interrupt management tests
# ---------------------------------------------------------------------------


class TestAgentServiceInterrupt:
    """Tests for interrupt management methods on AgentService."""

    def test_get_pending_approval_returns_none_when_empty(self) -> None:
        svc = AgentService()
        assert svc.get_pending_approval("thread-1") is None

    def test_get_pending_approval_returns_pending(self) -> None:
        svc = AgentService()
        pending = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="a1",
            interrupt_data={"tool_name": "web_search", "tool_args": {"query": "test"}},
        )
        svc._pending_interrupts["thread-1"] = pending
        assert svc.get_pending_approval("thread-1") is pending

    @pytest.mark.asyncio
    async def test_resolve_interrupt_approve(self) -> None:
        svc = AgentService()
        pending = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="a1",
            interrupt_data={"tool_name": "web_search"},
        )
        svc._pending_interrupts["thread-1"] = pending

        result = await svc.resolve_interrupt("thread-1", decision="approve")
        assert result is True
        assert pending.decision == {"type": "approve", "reason": None, "modified_args": None}
        assert pending.decision_event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_interrupt_edit(self) -> None:
        svc = AgentService()
        pending = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="a1",
            interrupt_data={"tool_name": "web_search"},
        )
        svc._pending_interrupts["thread-1"] = pending

        modified = {"query": "better search"}
        result = await svc.resolve_interrupt(
            "thread-1", decision="edit", modified_args=modified,
        )
        assert result is True
        assert pending.decision["type"] == "edit"
        assert pending.decision["modified_args"] == modified
        assert pending.decision_event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_interrupt_reject_with_reason(self) -> None:
        svc = AgentService()
        pending = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="a1",
            interrupt_data={"tool_name": "web_search"},
        )
        svc._pending_interrupts["thread-1"] = pending

        result = await svc.resolve_interrupt("thread-1", decision="reject", reason="Not safe")
        assert result is True
        assert pending.decision["type"] == "reject"
        assert pending.decision["reason"] == "Not safe"
        assert pending.decision_event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_interrupt_returns_false_when_no_pending(self) -> None:
        svc = AgentService()
        result = await svc.resolve_interrupt("nonexistent", decision="approve")
        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_approval_backward_compat_approve(self) -> None:
        """The old resolve_approval(approved=True) interface still works."""
        svc = AgentService()
        pending = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="a1",
            interrupt_data={"tool_name": "web_search"},
        )
        svc._pending_interrupts["thread-1"] = pending

        result = await svc.resolve_approval("thread-1", approved=True)
        assert result is True
        assert pending.decision["type"] == "approve"

    @pytest.mark.asyncio
    async def test_resolve_approval_backward_compat_reject(self) -> None:
        """The old resolve_approval(approved=False) interface still works."""
        svc = AgentService()
        pending = _PendingInterrupt(
            thread_id="thread-1",
            approval_id="a1",
            interrupt_data={"tool_name": "web_search"},
        )
        svc._pending_interrupts["thread-1"] = pending

        result = await svc.resolve_approval("thread-1", approved=False, reason="No")
        assert result is True
        assert pending.decision["type"] == "reject"
        assert pending.decision["reason"] == "No"


# ---------------------------------------------------------------------------
# SSE event encoding tests for approval event types
# ---------------------------------------------------------------------------


class TestApprovalSSEEvents:
    """Tests for approval-related SSE event types."""

    def test_encode_approval_required_event(self) -> None:
        evt = SSEEvent(
            event="approval_required",
            data={
                "approval_id": "a1",
                "thread_id": "t1",
                "tool_name": "web_search",
                "tool_args": {"query": "test"},
                "run_id": "r1",
                "allowed_decisions": ["approve", "edit", "reject"],
            },
        )
        encoded = evt.encode()
        assert "event: approval_required" in encoded
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["approval_id"] == "a1"
        assert parsed["tool_name"] == "web_search"
        assert parsed["allowed_decisions"] == ["approve", "edit", "reject"]

    def test_encode_approval_result_approved(self) -> None:
        evt = SSEEvent(
            event="approval_result",
            data={
                "approval_id": "a1",
                "decision": "approved",
                "tool_name": "web_search",
            },
        )
        encoded = evt.encode()
        assert "event: approval_result" in encoded
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["decision"] == "approved"

    def test_encode_approval_result_edited(self) -> None:
        evt = SSEEvent(
            event="approval_result",
            data={
                "approval_id": "a1",
                "decision": "edited",
                "tool_name": "web_search",
                "modified_args": {"query": "improved search"},
            },
        )
        encoded = evt.encode()
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["decision"] == "edited"
        assert parsed["modified_args"]["query"] == "improved search"

    def test_encode_approval_result_rejected(self) -> None:
        evt = SSEEvent(
            event="approval_result",
            data={
                "approval_id": "a1",
                "decision": "rejected",
                "tool_name": "web_search",
                "reason": "Too dangerous",
            },
        )
        encoded = evt.encode()
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["decision"] == "rejected"
        assert parsed["reason"] == "Too dangerous"


# ---------------------------------------------------------------------------
# interrupt_on configuration test
# ---------------------------------------------------------------------------


class TestInterruptOnConfig:
    """Tests that the interrupt_on configuration is correct."""

    def test_interrupt_on_is_dict(self) -> None:
        assert isinstance(INTERRUPT_ON, dict)

    def test_web_search_has_allowed_decisions(self) -> None:
        cfg = INTERRUPT_ON["web_search"]
        assert isinstance(cfg, dict)
        assert "allowed_decisions" in cfg
        assert "edit" in cfg["allowed_decisions"]

    def test_search_knowledge_base_configured(self) -> None:
        assert "search_knowledge_base" in INTERRUPT_ON

    def test_backward_compat_tools_requiring_approval(self) -> None:
        """TOOLS_REQUIRING_APPROVAL is a set of tool names from INTERRUPT_ON."""
        assert isinstance(TOOLS_REQUIRING_APPROVAL, set)
        assert "web_search" in TOOLS_REQUIRING_APPROVAL
        assert "search_knowledge_base" in TOOLS_REQUIRING_APPROVAL


# ---------------------------------------------------------------------------
# Approval endpoint integration tests
# ---------------------------------------------------------------------------


class TestApprovalEndpoint:
    """Integration tests for POST /chat/approval."""

    @pytest.mark.asyncio
    async def test_approval_no_pending_returns_404(self, client: AsyncClient) -> None:
        """Submitting a decision when no approval is pending should 404."""
        resp = await client.post(
            "/chat/approval",
            json={
                "thread_id": "nonexistent-thread",
                "decision": "approve",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approval_invalid_decision_returns_422(self, client: AsyncClient) -> None:
        """An invalid decision value should return 422."""
        resp = await client.post(
            "/chat/approval",
            json={
                "thread_id": "any-thread",
                "decision": "maybe",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_approval_approve_resolves(self, client: AsyncClient) -> None:
        """Approving a pending interrupt should succeed."""
        from app.services.agent_service import agent_service

        pending = _PendingInterrupt(
            thread_id="test-thread",
            approval_id="test-approval",
            interrupt_data={"tool_name": "web_search", "tool_args": {"query": "test"}},
        )
        agent_service._pending_interrupts["test-thread"] = pending

        try:
            resp = await client.post(
                "/chat/approval",
                json={
                    "thread_id": "test-thread",
                    "decision": "approve",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["decision"] == "approve"
            assert pending.decision["type"] == "approve"
        finally:
            agent_service._pending_interrupts.pop("test-thread", None)

    @pytest.mark.asyncio
    async def test_approval_edit_resolves(self, client: AsyncClient) -> None:
        """Editing a pending interrupt should pass modified args."""
        from app.services.agent_service import agent_service

        pending = _PendingInterrupt(
            thread_id="test-thread-edit",
            approval_id="test-approval-edit",
            interrupt_data={"tool_name": "web_search", "tool_args": {"query": "original"}},
        )
        agent_service._pending_interrupts["test-thread-edit"] = pending

        try:
            resp = await client.post(
                "/chat/approval",
                json={
                    "thread_id": "test-thread-edit",
                    "decision": "edit",
                    "modified_args": {"query": "improved"},
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["decision"] == "edit"
            assert pending.decision["type"] == "edit"
            assert pending.decision["modified_args"] == {"query": "improved"}
        finally:
            agent_service._pending_interrupts.pop("test-thread-edit", None)

    @pytest.mark.asyncio
    async def test_approval_reject_with_reason(self, client: AsyncClient) -> None:
        """Rejecting with a reason should store the reason."""
        from app.services.agent_service import agent_service

        pending = _PendingInterrupt(
            thread_id="test-thread-2",
            approval_id="test-approval-2",
            interrupt_data={"tool_name": "web_search", "tool_args": {}},
        )
        agent_service._pending_interrupts["test-thread-2"] = pending

        try:
            resp = await client.post(
                "/chat/approval",
                json={
                    "thread_id": "test-thread-2",
                    "decision": "reject",
                    "reason": "Not appropriate",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["decision"] == "reject"
            assert pending.decision["type"] == "reject"
            assert pending.decision["reason"] == "Not appropriate"
        finally:
            agent_service._pending_interrupts.pop("test-thread-2", None)


# ---------------------------------------------------------------------------
# GET /chat/approval/{thread_id} tests
# ---------------------------------------------------------------------------


class TestGetPendingApproval:
    """Integration tests for GET /chat/approval/{thread_id}."""

    @pytest.mark.asyncio
    async def test_no_pending_returns_has_pending_false(self, client: AsyncClient) -> None:
        resp = await client.get("/chat/approval/nonexistent-thread")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_pending"] is False

    @pytest.mark.asyncio
    async def test_pending_returns_approval_details(self, client: AsyncClient) -> None:
        from app.services.agent_service import agent_service

        pending = _PendingInterrupt(
            thread_id="thread-check",
            approval_id="pa-1",
            interrupt_data={
                "tool_name": "search_knowledge_base",
                "tool_args": {"query": "architecture"},
                "run_id": "run-check",
                "allowed_decisions": ["approve", "reject"],
            },
        )
        agent_service._pending_interrupts["thread-check"] = pending

        try:
            resp = await client.get("/chat/approval/thread-check")
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_pending"] is True
            assert data["approval_id"] == "pa-1"
            assert data["tool_name"] == "search_knowledge_base"
            assert data["tool_args"]["query"] == "architecture"
            assert data["allowed_decisions"] == ["approve", "reject"]
        finally:
            agent_service._pending_interrupts.pop("thread-check", None)
