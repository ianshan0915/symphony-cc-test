"""SSE streaming chat endpoint."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.message import Message
from app.models.thread import Thread
from app.services.agent_service import SSEEvent, agent_service
from app.services.thread_service import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Payload for the chat streaming endpoint."""

    message: str = Field(..., min_length=1, max_length=32_000, description="User message text")
    model: str | None = Field(default=None, description="Optional model override")


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
    tool_calls: list | None = None,
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


@router.post("/stream", response_class=StreamingResponse)
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
    - ``tool_call`` — agent invokes a tool
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

    async def _event_generator():
        """Generate SSE events from the agent and persist the result."""
        full_content = ""
        tool_calls = []

        async for sse_event in agent_service.stream_response(
            thread_id=str(thread.id),
            user_message=body.message,
            thread=thread,
        ):
            # Capture final content for persistence
            if sse_event.event == "message_end":
                full_content = sse_event.data.get("content", "")
                tool_calls = sse_event.data.get("tool_calls") or []

            yield sse_event.encode()

        # Persist assistant response after streaming completes
        if full_content:
            try:
                await _persist_assistant_message(
                    session, thread, full_content, tool_calls or None
                )
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
