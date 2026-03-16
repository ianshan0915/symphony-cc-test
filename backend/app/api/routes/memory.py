"""Memory management endpoints — read and update persistent AGENTS.md.

The ``/memories/AGENTS.md`` file is loaded by agents at the start of every
conversation (via ``memory=["/memories/AGENTS.md"]`` in ``create_deep_agent``).
Updating it here lets users inject project conventions, preferences, and
long-term context that agents will see in every thread.

Endpoints
---------
GET  /memory    — Retrieve the current AGENTS.md content.
PUT  /memory    — Replace the AGENTS.md content.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.middleware import get_agents_md, set_agents_md
from app.api.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/memory",
    tags=["memory"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MemoryResponse(BaseModel):
    """Response body for GET /memory."""

    content: str = Field(..., description="Current AGENTS.md Markdown content")


class MemoryUpdate(BaseModel):
    """Request body for PUT /memory."""

    content: str = Field(
        ...,
        description="New AGENTS.md Markdown content",
        max_length=524_288,  # 512 KiB — guard against runaway payloads
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=MemoryResponse)
async def get_memory() -> MemoryResponse:
    """Retrieve the current AGENTS.md persistent memory content.

    This file is loaded by agents at conversation start, providing
    persistent context across all threads.

    Auth is enforced by the router-level dependency; no ``user`` argument
    is needed here because the endpoint does not act on user identity.
    ``get_agents_md()`` never raises — it falls back to the default content
    on any store error — so no try/except is required.
    """
    content = await get_agents_md()
    return MemoryResponse(content=content)


@router.put("", response_model=MemoryResponse)
async def update_memory(
    body: MemoryUpdate,
    user: User = Depends(get_current_user),
) -> MemoryResponse:
    """Replace the AGENTS.md persistent memory content.

    The new content will be loaded by agents at the start of future
    conversations, enabling personalisation and project-level context
    to persist across threads.
    """
    try:
        await set_agents_md(body.content)
    except Exception as exc:
        logger.error("Failed to write AGENTS.md to store: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory store unavailable",
        ) from exc
    logger.info("AGENTS.md updated by user %s", user.id)
    return MemoryResponse(content=body.content)
