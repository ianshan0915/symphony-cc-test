"""Assistant configuration service — CRUD operations for assistant configs."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assistant import Assistant, AssistantCreate, AssistantUpdate
from app.models.skill import Skill

logger = logging.getLogger(__name__)


class AssistantService:
    """CRUD operations for assistant configurations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _resolve_skills(self, skill_ids: list[uuid.UUID]) -> list[Skill]:
        """Validate skill_ids exist and are accessible, return Skill objects.

        Skills are accessible if they are system-wide (user_id=NULL) or
        user-owned. For now we validate existence only; ownership checks
        can be layered on when multi-tenancy requires it.
        """
        if not skill_ids:
            return []
        result = await self._session.execute(
            select(Skill).where(
                Skill.id.in_(skill_ids),
                Skill.is_active.is_(True),
            )
        )
        found = list(result.scalars().all())
        found_ids = {s.id for s in found}
        missing = set(skill_ids) - found_ids
        if missing:
            raise ValueError(
                f"Skills not found or inactive: {[str(m) for m in missing]}"
            )
        return found

    async def create(self, data: AssistantCreate, *, user_id: uuid.UUID | None = None) -> Assistant:
        """Create a new assistant configuration.

        When *user_id* is provided the assistant is owned by that user.
        When ``None`` the assistant is system-owned (visible to everyone).
        """
        # Resolve skills if provided
        skills = await self._resolve_skills(data.skill_ids)

        assistant = Assistant(
            name=data.name,
            description=data.description,
            model=data.model,
            system_prompt=data.system_prompt,
            tools_enabled=data.tools_enabled,
            metadata_=data.metadata,
            user_id=user_id,
        )
        if skills:
            assistant.skills = skills

        self._session.add(assistant)
        await self._session.commit()
        await self._session.refresh(assistant)
        return assistant

    async def get(
        self, assistant_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> Assistant | None:
        """Get an assistant configuration by ID.

        Access is granted to system assistants (``user_id IS NULL``) and
        assistants owned by *user_id*.
        """
        query = (
            select(Assistant)
            .options(selectinload(Assistant.skills))
            .where(
                Assistant.id == assistant_id,
                Assistant.is_active.is_(True),
            )
        )
        if user_id is not None:
            query = query.where(
                or_(Assistant.user_id.is_(None), Assistant.user_id == user_id)
            )

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        user_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
        active_only: bool = True,
    ) -> tuple[list[Assistant], int]:
        """List assistant configurations with pagination.

        Returns system assistants (``user_id IS NULL``) plus assistants
        owned by *user_id* when provided.
        """
        base_query = select(Assistant)
        if active_only:
            base_query = base_query.where(Assistant.is_active.is_(True))

        if user_id is not None:
            base_query = base_query.where(
                or_(Assistant.user_id.is_(None), Assistant.user_id == user_id)
            )

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        # Fetch page ordered by creation date
        query = (
            base_query.options(selectinload(Assistant.skills))
            .order_by(Assistant.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        assistants = list(result.scalars().all())

        # Sort default assistants first (stable sort preserves created_at order)
        assistants.sort(
            key=lambda a: 0 if (a.metadata_ or {}).get("is_default") is True else 1,
        )

        return assistants, total

    async def update(
        self,
        assistant_id: uuid.UUID,
        data: AssistantUpdate,
        *,
        user_id: uuid.UUID | None = None,
    ) -> Assistant | None:
        """Update an assistant configuration.

        Only user-owned assistants can be updated.  System assistants
        (``user_id IS NULL``) are read-only.

        Raises ``PermissionError`` if the caller tries to modify a system
        assistant.
        """
        assistant = await self.get(assistant_id, user_id=user_id)
        if assistant is None:
            return None

        # Prevent modification of system assistants
        if assistant.user_id is None:
            raise PermissionError("System assistants cannot be modified")

        # Ensure user owns the assistant
        if user_id is not None and assistant.user_id != user_id:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Handle skill_ids separately
        if "skill_ids" in update_data:
            skill_ids = update_data.pop("skill_ids")
            skills = await self._resolve_skills(skill_ids)
            assistant.skills = skills

        # Map 'metadata' field to 'metadata_' column
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")

        for field, value in update_data.items():
            setattr(assistant, field, value)

        await self._session.commit()
        await self._session.refresh(assistant)
        return assistant

    async def delete(
        self, assistant_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> bool:
        """Soft-delete an assistant configuration (set is_active=False).

        Only user-owned assistants can be deleted.  System assistants
        (``user_id IS NULL``) are read-only.

        Raises ``PermissionError`` if the caller tries to delete a system
        assistant.
        """
        assistant = await self.get(assistant_id, user_id=user_id)
        if assistant is None:
            return False

        # Prevent deletion of system assistants
        if assistant.user_id is None:
            raise PermissionError("System assistants cannot be deleted")

        # Ensure user owns the assistant
        if user_id is not None and assistant.user_id != user_id:
            return False

        assistant.is_active = False
        await self._session.commit()
        return True

    async def count(self, *, active_only: bool = True) -> int:
        """Return the total number of assistants."""
        query = select(func.count()).select_from(Assistant)
        if active_only:
            query = query.where(Assistant.is_active.is_(True))
        result = await self._session.execute(query)
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Default assistant seed data
# ---------------------------------------------------------------------------

DEFAULT_ASSISTANTS: list[dict[str, object]] = [
    {
        "name": "General Assistant",
        "description": "A general-purpose AI assistant that can help with a wide range of tasks.",
        "type": "general",
    },
    {
        "name": "Researcher",
        "description": (
            "An expert research assistant focused on web search, fact-finding, and citation."
        ),
        "type": "researcher",
    },
    {
        "name": "Coder",
        "description": (
            "An expert software engineering assistant for writing, reviewing, and debugging code."
        ),
        "type": "coder",
    },
    {
        "name": "Writer",
        "description": "An expert writing assistant for content creation, editing, and refinement.",
        "type": "writer",
    },
]


async def seed_default_assistants(session: AsyncSession) -> None:
    """Create default assistants if the assistants table is empty.

    This is called once at application startup to ensure new deployments
    have a usable set of assistants in the dropdown selector.

    Default assistants are seeded with skills matching their agent type
    when matching skills exist in the database.
    """
    from app.agents.prompts import AGENT_PROMPT_REGISTRY, get_skills_for_agent_type

    svc = AssistantService(session)
    existing = await svc.count(active_only=False)
    if existing > 0:
        logger.debug("Assistants table already has %d rows — skipping seed", existing)
        return

    # Pre-fetch all active skills for assignment
    skill_result = await session.execute(
        select(Skill).where(Skill.is_active.is_(True))
    )
    all_skills = {s.name: s for s in skill_result.scalars().all()}

    logger.info("Seeding %d default assistants", len(DEFAULT_ASSISTANTS))
    for entry in DEFAULT_ASSISTANTS:
        agent_type = str(entry["type"])
        registry_entry = AGENT_PROMPT_REGISTRY.get(agent_type, {})
        system_prompt = registry_entry.get("system_prompt")
        raw_tools = registry_entry.get("tools")
        tools: list[str] = list(raw_tools) if raw_tools else []

        # Resolve skills for this agent type
        type_skill_names = get_skills_for_agent_type(agent_type)
        skill_ids: list[uuid.UUID] = []
        if type_skill_names is not None:
            for sname in type_skill_names:
                if sname in all_skills:
                    skill_ids.append(all_skills[sname].id)
        else:
            # None means "all skills" for general type
            skill_ids = [s.id for s in all_skills.values()]

        data = AssistantCreate(
            name=str(entry["name"]),
            description=str(entry["description"]),
            model="gpt-4o",
            system_prompt=str(system_prompt) if system_prompt else None,
            tools_enabled=tools,
            metadata={"agent_type": agent_type, "is_default": True},
            skill_ids=skill_ids,
        )
        assistant = await svc.create(data)
        logger.info(
            "Seeded assistant %r (id=%s, skills=%d)",
            assistant.name,
            assistant.id,
            len(skill_ids),
        )

    logger.info("Default assistant seeding complete")
