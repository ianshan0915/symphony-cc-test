"""SSE streaming chat endpoint with human-in-the-loop approval support."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, rate_limiter, rate_limiter_strict, set_request_user_id
from app.models.message import Message
from app.models.thread import Thread
from app.services.agent_service import SSEEvent, agent_service
from app.services.thread_service import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(set_request_user_id)],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Payload for the chat streaming endpoint."""

    message: str = Field(..., min_length=1, max_length=32_000, description="User message text")
    model: str | None = Field(default=None, description="Optional model override")
    assistant_type: str | None = Field(
        default=None,
        description="Agent specialization type: 'researcher', 'coder', 'writer', or 'general'",
    )


class ApprovalDecisionRequest(BaseModel):
    """Payload for approving or rejecting a pending tool call."""

    thread_id: str = Field(..., description="Thread ID with a pending approval")
    decision: str = Field(..., pattern="^(approve|reject)$", description="approve or reject")
    reason: str | None = Field(default=None, description="Optional reason for rejection")


class ApprovalDecisionResponse(BaseModel):
    """Response after processing an approval decision."""

    success: bool
    thread_id: str
    decision: str
    message: str


class PendingApprovalResponse(BaseModel):
    """Response showing the current pending approval for a thread."""

    has_pending: bool
    approval_id: str | None = None
    thread_id: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    run_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _persist_user_message(
    session: AsyncSession,
    thread: Thread,
    content: str,
) -> Message:
    """Persist the user's message to the database."""
    msg = Message(
        thread_id=thread.id,
        role="user",
        content=content,
        metadata_={},
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def _persist_assistant_message(
    session: AsyncSession,
    thread: Thread,
    content: str,
    tool_calls: list[Any] | None = None,
) -> Message:
    """Persist the assistant's response to the database."""
    msg = Message(
        thread_id=thread.id,
        role="assistant",
        content=content,
        tool_calls={"calls": tool_calls} if tool_calls else None,
        metadata_={},
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/stream",
    response_class=StreamingResponse,
    dependencies=[Depends(rate_limiter_strict)],
)
async def chat_stream(
    body: ChatRequest,
    thread_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream an agent response as Server-Sent Events.

    Accepts a user message and an optional ``thread_id`` query parameter.
    If no thread_id is provided, a new thread is created automatically.

    **SSE event types:**

    - ``message_start`` — assistant turn begins
    - ``token`` — incremental text token
    - ``tool_call`` — agent invokes a tool (auto-approved)
    - ``approval_required`` — agent wants to invoke a tool that requires approval
    - ``approval_result`` — user approved or rejected the tool call
    - ``tool_result`` — tool execution result
    - ``message_end`` — assistant turn complete (includes full content)
    - ``error`` — an error occurred during processing
    """
    thread_svc = ThreadService(session)

    # Resolve or create thread
    thread: Thread | None = None
    if thread_id is not None:
        thread = await thread_svc.get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found")
    else:
        from app.models.thread import ThreadCreate

        thread = await thread_svc.create(
            ThreadCreate(title=body.message[:80], assistant_id="default")
        )

    # Persist user message
    await _persist_user_message(session, thread, body.message)

    async def _event_generator() -> Any:
        """Generate SSE events from the agent and persist the result."""
        full_content = ""
        tool_calls: list[Any] = []

        async for sse_event in agent_service.stream_response(
            thread_id=str(thread.id),
            user_message=body.message,
            thread=thread,
            assistant_type=body.assistant_type,
        ):
            # Capture final content for persistence
            if sse_event.event == "message_end":
                full_content = sse_event.data.get("content", "")
                tool_calls = sse_event.data.get("tool_calls") or []

            yield sse_event.encode()

        # Persist assistant response after streaming completes
        if full_content:
            try:
                await _persist_assistant_message(session, thread, full_content, tool_calls or None)
            except Exception:
                logger.exception("Failed to persist assistant message for thread %s", thread.id)
                yield SSEEvent(
                    event="error",
                    data={"error": "Failed to save assistant message"},
                ).encode()

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Approval decision endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/approval",
    response_model=ApprovalDecisionResponse,
    dependencies=[Depends(rate_limiter)],
)
async def submit_approval_decision(
    body: ApprovalDecisionRequest,
) -> ApprovalDecisionResponse:
    """Submit an approval or rejection decision for a pending tool call.

    When the agent encounters a tool that requires human approval, the SSE
    stream emits an ``approval_required`` event and pauses execution.  The
    frontend should call this endpoint to approve or reject the tool call,
    which unblocks the stream.

    **Request body:**

    - ``thread_id`` — the thread with a pending approval
    - ``decision`` — ``"approve"`` or ``"reject"``
    - ``reason`` — optional reason for rejection
    """
    approved = body.decision == "approve"
    resolved = await agent_service.resolve_approval(
        thread_id=body.thread_id,
        approved=approved,
        reason=body.reason,
    )

    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval found for thread {body.thread_id}",
        )

    decision_label = "approved" if approved else "rejected"
    return ApprovalDecisionResponse(
        success=True,
        thread_id=body.thread_id,
        decision=body.decision,
        message=f"Tool call {decision_label} successfully",
    )


# ---------------------------------------------------------------------------
# Pending approval query endpoint
# ---------------------------------------------------------------------------


@router.get("/approval/{thread_id}", response_model=PendingApprovalResponse)
async def get_pending_approval(thread_id: str) -> PendingApprovalResponse:
    """Check if a thread has a pending approval request.

    Returns approval details if one is pending, or ``has_pending: false``
    otherwise.
    """
    pending = agent_service.get_pending_approval(thread_id)
    if pending is None:
        return PendingApprovalResponse(has_pending=False)

    return PendingApprovalResponse(
        has_pending=True,
        approval_id=pending.approval_id,
        thread_id=pending.thread_id,
        tool_name=pending.tool_name,
        tool_args=pending.tool_args,
        run_id=pending.run_id,
    )
