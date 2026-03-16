"""Assistant configuration CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_assistant_service, get_current_user
from app.models.assistant import (
    AssistantCreate,
    AssistantListResponse,
    AssistantOut,
    AssistantUpdate,
)
from app.models.user import User
from app.services.assistant_service import AssistantService

router = APIRouter(
    prefix="/assistants",
    tags=["assistants"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=AssistantOut, status_code=201)
async def create_assistant(
    body: AssistantCreate,
    current_user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantOut:
    """Create a new assistant configuration owned by the current user."""
    try:
        assistant = await service.create(body, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AssistantOut.model_validate(assistant)


@router.get("", response_model=AssistantListResponse)
async def list_assistants(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantListResponse:
    """List available assistant configurations.

    Returns system assistants (visible to all) plus the current user's
    own assistants.
    """
    assistants, total = await service.list(
        user_id=current_user.id, offset=offset, limit=limit
    )
    return AssistantListResponse(
        assistants=[AssistantOut.model_validate(a) for a in assistants],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{assistant_id}", response_model=AssistantOut)
async def get_assistant(
    assistant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantOut:
    """Get an assistant configuration by ID.

    Users can access system assistants and their own assistants.
    """
    assistant = await service.get(assistant_id, user_id=current_user.id)
    if assistant is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return AssistantOut.model_validate(assistant)


@router.put("/{assistant_id}", response_model=AssistantOut)
async def update_assistant(
    assistant_id: uuid.UUID,
    body: AssistantUpdate,
    current_user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantOut:
    """Update an assistant configuration.

    Only user-owned assistants can be modified. System assistants are
    read-only.
    """
    try:
        assistant = await service.update(
            assistant_id, body, user_id=current_user.id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if assistant is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return AssistantOut.model_validate(assistant)


@router.delete("/{assistant_id}", status_code=204)
async def delete_assistant(
    assistant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> None:
    """Soft-delete an assistant configuration.

    Only user-owned assistants can be deleted. System assistants are
    read-only.
    """
    try:
        deleted = await service.delete(assistant_id, user_id=current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Assistant not found")
