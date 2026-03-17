"""SSE streaming chat endpoint with human-in-the-loop approval support."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.middleware import get_agents_md_modified_at
from app.agents.response_formats import RESPONSE_FORMAT_REGISTRY
from app.api.deps import (
    get_current_user,
    get_db_session,
    rate_limiter,
    rate_limiter_strict,
    set_request_user_id,
)
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User
from app.services.agent_service import _DECISION_PAST_TENSE, agent_service
from app.services.assistant_service import AssistantService
from app.services.sse import SSEEvent
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
    assistant_id: str | None = Field(
        default=None,
        description="Assistant UUID to associate the thread with",
    )
    assistant_type: str | None = Field(
        default=None,
        description="Agent specialization type: 'researcher', 'coder', 'writer', or 'general'",
    )
    response_format: str | None = Field(
        default=None,
        description=(
            "Named response format for structured output.  One of: "
            "'data_extraction', 'report', 'form_fill', 'api_integration'.  "
            "When set the agent constrains its final response to the "
            "corresponding JSON schema and the message_end SSE event will "
            "include a 'structured_response' field.  Overrides any "
            "response_format configured on the assistant."
        ),
    )


class ApprovalDecisionRequest(BaseModel):
    """Payload for approving, editing, or rejecting a pending tool call."""

    thread_id: str = Field(..., description="Thread ID with a pending approval")
    decision: str = Field(
        ...,
        pattern="^(approve|edit|reject)$",
        description="approve, edit, or reject",
    )
    reason: str | None = Field(default=None, description="Optional reason for rejection")
    modified_args: dict[str, Any] | None = Field(
        default=None,
        description="Modified tool arguments (required when decision is 'edit')",
    )


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
    allowed_decisions: list[str] | None = None


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
    assistant_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream an agent response as Server-Sent Events.

    Accepts a user message and optional query parameters:

    - ``thread_id`` — existing thread to continue; a new thread is created if omitted.
    - ``assistant_id`` — assistant whose ``agent_type`` metadata determines routing.

    **SSE event types:**

    - ``message_start`` — assistant turn begins
    - ``token`` — incremental text token
    - ``tool_call`` — agent invokes a tool (auto-approved)
    - ``approval_required`` — agent wants to invoke a tool that requires approval
    - ``approval_result`` — user approved or rejected the tool call
    - ``tool_result`` — tool execution result
    - ``message_end`` — assistant turn complete (includes full content)
    - ``memory_updated`` — agent saved new memories during the conversation
    - ``error`` — an error occurred during processing
    """
    thread_svc = ThreadService(session)

    # Resolve assistant_type and response_format from assistant_id or request body
    assistant_type = body.assistant_type
    # Start with the request-level response_format (takes precedence)
    response_format_name: str | None = body.response_format
    if assistant_id is not None and (assistant_type is None or response_format_name is None):
        assistant_svc = AssistantService(session)
        assistant = await assistant_svc.get(assistant_id, user_id=current_user.id)
        if assistant is not None:
            meta = assistant.metadata_ or {}
            if assistant_type is None:
                assistant_type = meta.get("agent_type")
            # Use assistant-configured response_format only when not overridden in request
            if response_format_name is None:
                response_format_name = meta.get("response_format")
        else:
            logger.warning("Assistant %s not found, falling back to default agent", assistant_id)

    # Resolve the named format to a Pydantic class
    from pydantic import BaseModel as _BaseModel

    resolved_response_format: type[_BaseModel] | None = None
    if response_format_name is not None:
        resolved_response_format = RESPONSE_FORMAT_REGISTRY.get(response_format_name)
        if resolved_response_format is None:
            logger.warning(
                "Unknown response_format %r — ignoring (valid choices: %s)",
                response_format_name,
                ", ".join(RESPONSE_FORMAT_REGISTRY),
            )

    # Resolve or create thread
    thread: Thread | None = None
    if thread_id is not None:
        thread = await thread_svc.get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found")
    else:
        from app.models.thread import ThreadCreate

        aid = str(assistant_id) if assistant_id else "default"
        thread = await thread_svc.create(ThreadCreate(title=body.message[:80], assistant_id=aid))

    # Persist user message
    await _persist_user_message(session, thread, body.message)

    async def _event_generator() -> Any:
        """Generate SSE events from the agent and persist the result."""
        full_content = ""
        tool_calls: list[Any] = []

        # Snapshot the AGENTS.md modification timestamp before the agent runs.
        # We compare timestamps (not full content) after the run to detect
        # whether the agent saved new memories — avoids reconstructing and
        # comparing potentially large content strings.
        user_id_str = str(current_user.id)
        modified_at_before = await get_agents_md_modified_at(user_id=user_id_str)

        async for sse_event in agent_service.stream_response(
            thread_id=str(thread.id),
            user_message=body.message,
            thread=thread,
            assistant_type=assistant_type,
            user_id=user_id_str,
            response_format=resolved_response_format,
        ):
            # Capture final content for persistence
            if sse_event.event == "message_end":
                full_content = sse_event.data.get("content", "")
                tool_calls = sse_event.data.get("tool_calls") or []

            yield sse_event.encode()

        # Emit memory_updated if the agent changed the user's AGENTS.md.
        try:
            modified_at_after = await get_agents_md_modified_at(user_id=user_id_str)
            if modified_at_after is not None and modified_at_after != modified_at_before:
                yield SSEEvent(
                    event="memory_updated",
                    data={"thread_id": str(thread.id)},
                ).encode()
        except Exception:
            logger.debug("Failed to compare AGENTS.md timestamps after agent run", exc_info=True)

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
    """Submit an approval, edit, or rejection decision for a pending tool call.

    When the agent encounters a tool configured in ``interrupt_on``, the SSE
    stream emits an ``approval_required`` event and pauses execution.  The
    frontend should call this endpoint to approve, edit, or reject the tool
    call, which unblocks the stream.

    **Request body:**

    - ``thread_id`` — the thread with a pending approval
    - ``decision`` — ``"approve"``, ``"edit"``, or ``"reject"``
    - ``reason`` — optional reason for rejection
    - ``modified_args`` — modified tool arguments (when decision is ``"edit"``)
    """
    resolved = await agent_service.resolve_interrupt(
        body.thread_id,
        decision=body.decision,
        reason=body.reason,
        modified_args=body.modified_args,
    )

    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval found for thread {body.thread_id}",
        )

    decision_label = _DECISION_PAST_TENSE.get(body.decision, body.decision)
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

    interrupt = pending.interrupt_data
    return PendingApprovalResponse(
        has_pending=True,
        approval_id=pending.approval_id,
        thread_id=pending.thread_id,
        tool_name=interrupt.get("tool_name"),
        tool_args=interrupt.get("tool_args"),
        run_id=interrupt.get("run_id"),
        allowed_decisions=interrupt.get("allowed_decisions"),
    )
