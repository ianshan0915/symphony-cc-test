"""Assistant configuration CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_assistant_service
from app.models.assistant import (
    AssistantCreate,
    AssistantListResponse,
    AssistantOut,
    AssistantUpdate,
)
from app.services.assistant_service import AssistantService

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.post("", response_model=AssistantOut, status_code=201)
async def create_assistant(
    body: AssistantCreate,
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantOut:
    """Create a new assistant configuration."""
    assistant = await service.create(body)
    return AssistantOut.model_validate(assistant)


@router.get("", response_model=AssistantListResponse)
async def list_assistants(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantListResponse:
    """List available assistant configurations."""
    assistants, total = await service.list(offset=offset, limit=limit)
    return AssistantListResponse(
        assistants=[AssistantOut.model_validate(a) for a in assistants],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{assistant_id}", response_model=AssistantOut)
async def get_assistant(
    assistant_id: uuid.UUID,
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantOut:
    """Get an assistant configuration by ID."""
    assistant = await service.get(assistant_id)
    if assistant is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return AssistantOut.model_validate(assistant)


@router.put("/{assistant_id}", response_model=AssistantOut)
async def update_assistant(
    assistant_id: uuid.UUID,
    body: AssistantUpdate,
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantOut:
    """Update an assistant configuration."""
    assistant = await service.update(assistant_id, body)
    if assistant is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return AssistantOut.model_validate(assistant)


@router.delete("/{assistant_id}", status_code=204)
async def delete_assistant(
    assistant_id: uuid.UUID,
    service: AssistantService = Depends(get_assistant_service),
) -> None:
    """Soft-delete an assistant configuration."""
    deleted = await service.delete(assistant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assistant not found")
