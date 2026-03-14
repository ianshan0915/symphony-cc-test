"""Thread CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_thread_service
from app.models.thread import (
    DeleteResponse,
    ThreadCreate,
    ThreadDetail,
    ThreadListResponse,
    ThreadOut,
)
from app.services.thread_service import ThreadService

router = APIRouter(prefix="/threads", tags=["threads"])


@router.post("", response_model=ThreadOut, status_code=201)
async def create_thread(
    body: ThreadCreate,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadOut:
    """Create a new conversation thread."""
    thread = await service.create(body)
    return ThreadOut.model_validate(thread)


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadListResponse:
    """List conversation threads with pagination."""
    threads, total = await service.list(offset=offset, limit=limit)
    return ThreadListResponse(
        threads=[ThreadOut.model_validate(t) for t in threads],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: uuid.UUID,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetail:
    """Get a thread with its messages."""
    thread = await service.get(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadDetail.model_validate(thread)


@router.delete("/{thread_id}", response_model=DeleteResponse)
async def delete_thread(
    thread_id: uuid.UUID,
    service: ThreadService = Depends(get_thread_service),
) -> DeleteResponse:
    """Soft-delete a thread."""
    deleted = await service.delete(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return DeleteResponse()
