"""User-created skills CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_skill_service
from app.models.skill import (
    SkillCreate,
    SkillListResponse,
    SkillOut,
    SkillUpdate,
)
from app.models.user import User
from app.services.skill_service import SkillService

router = APIRouter(
    prefix="/skills",
    tags=["skills"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=SkillOut, status_code=201)
async def create_skill(
    body: SkillCreate,
    user: User = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> SkillOut:
    """Create a new user skill."""
    skill = await service.create(body, user_id=user.id)
    return SkillOut.model_validate(skill)


@router.get("", response_model=SkillListResponse)
async def list_skills(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> SkillListResponse:
    """List skills visible to the current user (system-wide + user's own)."""
    skills, total = await service.list(user.id, offset=offset, limit=limit)
    return SkillListResponse(
        skills=[SkillOut.model_validate(s) for s in skills],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> SkillOut:
    """Get a skill by ID.

    Users can see system-wide skills (user_id=NULL) and their own skills.
    """
    skill = await service.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    # Visibility check: system-wide or own skill
    if skill.user_id is not None and skill.user_id != user.id:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillOut.model_validate(skill)


@router.put("/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: uuid.UUID,
    body: SkillUpdate,
    user: User = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> SkillOut:
    """Update a user skill. Users can only edit their own skills."""
    skill = await service.update(skill_id, body, user_id=user.id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found or not owned by user")
    return SkillOut.model_validate(skill)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> None:
    """Soft-delete a user skill. Users can only delete their own skills."""
    deleted = await service.delete(skill_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill not found or not owned by user")
