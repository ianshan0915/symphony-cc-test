"""Tests for the human-in-the-loop approval flow (SYM-27)."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.services.agent_service import (
    TOOLS_REQUIRING_APPROVAL,
    AgentService,
    PendingApproval,
    SSEEvent,
)

# ---------------------------------------------------------------------------
# PendingApproval unit tests
# ---------------------------------------------------------------------------


class TestPendingApproval:
    """Unit tests for the PendingApproval dataclass."""

    def test_default_values(self) -> None:
        pa = PendingApproval(
            approval_id="test-id",
            thread_id="thread-1",
            tool_name="web_search",
            tool_args={"query": "test"},
            run_id="run-1",
        )
        assert pa.approved is None
        assert pa.reject_reason is None
        assert not pa.decision_event.is_set()

    def test_decision_event_signalling(self) -> None:
        pa = PendingApproval(
            approval_id="test-id",
            thread_id="thread-1",
            tool_name="web_search",
            tool_args={},
            run_id="run-1",
        )
        assert not pa.decision_event.is_set()
        pa.approved = True
        pa.decision_event.set()
        assert pa.decision_event.is_set()


# ---------------------------------------------------------------------------
# AgentService approval management tests
# ---------------------------------------------------------------------------


class TestAgentServiceApproval:
    """Tests for approval management methods on AgentService."""

    def test_get_pending_approval_returns_none_when_empty(self) -> None:
        svc = AgentService()
        assert svc.get_pending_approval("thread-1") is None

    def test_get_pending_approval_returns_pending(self) -> None:
        svc = AgentService()
        pending = PendingApproval(
            approval_id="a1",
            thread_id="thread-1",
            tool_name="web_search",
            tool_args={"query": "test"},
            run_id="r1",
        )
        svc._pending_approvals["thread-1"] = pending
        assert svc.get_pending_approval("thread-1") is pending

    @pytest.mark.asyncio
    async def test_resolve_approval_approve(self) -> None:
        svc = AgentService()
        pending = PendingApproval(
            approval_id="a1",
            thread_id="thread-1",
            tool_name="web_search",
            tool_args={},
            run_id="r1",
        )
        svc._pending_approvals["thread-1"] = pending

        result = await svc.resolve_approval("thread-1", approved=True)
        assert result is True
        assert pending.approved is True
        assert pending.decision_event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_approval_reject_with_reason(self) -> None:
        svc = AgentService()
        pending = PendingApproval(
            approval_id="a1",
            thread_id="thread-1",
            tool_name="web_search",
            tool_args={},
            run_id="r1",
        )
        svc._pending_approvals["thread-1"] = pending

        result = await svc.resolve_approval(
            "thread-1", approved=False, reason="Not safe"
        )
        assert result is True
        assert pending.approved is False
        assert pending.reject_reason == "Not safe"
        assert pending.decision_event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_approval_returns_false_when_no_pending(self) -> None:
        svc = AgentService()
        result = await svc.resolve_approval("nonexistent", approved=True)
        assert result is False


# ---------------------------------------------------------------------------
# SSE event encoding tests for new event types
# ---------------------------------------------------------------------------


class TestApprovalSSEEvents:
    """Tests for new approval-related SSE event types."""

    def test_encode_approval_required_event(self) -> None:
        evt = SSEEvent(
            event="approval_required",
            data={
                "approval_id": "a1",
                "thread_id": "t1",
                "tool_name": "web_search",
                "tool_args": {"query": "test"},
                "run_id": "r1",
            },
        )
        encoded = evt.encode()
        assert "event: approval_required" in encoded
        parsed = json.loads(encoded.split("data: ")[1].strip())
        assert parsed["approval_id"] == "a1"
        assert parsed["tool_name"] == "web_search"

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
# Tools requiring approval configuration test
# ---------------------------------------------------------------------------


class TestToolApprovalConfig:
    """Tests that the approval configuration is correct."""

    def test_tools_requiring_approval_is_set(self) -> None:
        assert isinstance(TOOLS_REQUIRING_APPROVAL, set)

    def test_web_search_requires_approval(self) -> None:
        assert "web_search" in TOOLS_REQUIRING_APPROVAL

    def test_search_knowledge_base_requires_approval(self) -> None:
        assert "search_knowledge_base" in TOOLS_REQUIRING_APPROVAL


# ---------------------------------------------------------------------------
# Approval endpoint integration tests
# ---------------------------------------------------------------------------


class TestApprovalEndpoint:
    """Integration tests for POST /chat/approval."""

    @pytest.mark.asyncio
    async def test_approval_no_pending_returns_404(
        self, client: AsyncClient
    ) -> None:
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
    async def test_approval_invalid_decision_returns_422(
        self, client: AsyncClient
    ) -> None:
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
    async def test_approval_approve_resolves(
        self, client: AsyncClient
    ) -> None:
        """Approving a pending approval should succeed."""
        from app.services.agent_service import agent_service

        # Manually inject a pending approval
        pending = PendingApproval(
            approval_id="test-approval",
            thread_id="test-thread",
            tool_name="web_search",
            tool_args={"query": "test"},
            run_id="run-1",
        )
        agent_service._pending_approvals["test-thread"] = pending

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
            assert pending.approved is True
        finally:
            agent_service._pending_approvals.pop("test-thread", None)

    @pytest.mark.asyncio
    async def test_approval_reject_with_reason(
        self, client: AsyncClient
    ) -> None:
        """Rejecting with a reason should store the reason."""
        from app.services.agent_service import agent_service

        pending = PendingApproval(
            approval_id="test-approval-2",
            thread_id="test-thread-2",
            tool_name="web_search",
            tool_args={},
            run_id="run-2",
        )
        agent_service._pending_approvals["test-thread-2"] = pending

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
            assert pending.approved is False
            assert pending.reject_reason == "Not appropriate"
        finally:
            agent_service._pending_approvals.pop("test-thread-2", None)


# ---------------------------------------------------------------------------
# GET /chat/approval/{thread_id} tests
# ---------------------------------------------------------------------------


class TestGetPendingApproval:
    """Integration tests for GET /chat/approval/{thread_id}."""

    @pytest.mark.asyncio
    async def test_no_pending_returns_has_pending_false(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/chat/approval/nonexistent-thread")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_pending"] is False

    @pytest.mark.asyncio
    async def test_pending_returns_approval_details(
        self, client: AsyncClient
    ) -> None:
        from app.services.agent_service import agent_service

        pending = PendingApproval(
            approval_id="pa-1",
            thread_id="thread-check",
            tool_name="search_knowledge_base",
            tool_args={"query": "architecture"},
            run_id="run-check",
        )
        agent_service._pending_approvals["thread-check"] = pending

        try:
            resp = await client.get("/chat/approval/thread-check")
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_pending"] is True
            assert data["approval_id"] == "pa-1"
            assert data["tool_name"] == "search_knowledge_base"
            assert data["tool_args"]["query"] == "architecture"
        finally:
            agent_service._pending_approvals.pop("thread-check", None)
