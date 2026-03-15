"""Assistant configuration service — CRUD operations for assistant configs."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantCreate, AssistantUpdate

logger = logging.getLogger(__name__)


class AssistantService:
    """CRUD operations for assistant configurations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: AssistantCreate) -> Assistant:
        """Create a new assistant configuration."""
        assistant = Assistant(
            name=data.name,
            description=data.description,
            model=data.model,
            system_prompt=data.system_prompt,
            tools_enabled=data.tools_enabled,
            metadata_=data.metadata,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
        self._session.add(assistant)
        await self._session.commit()
        await self._session.refresh(assistant)
        return assistant

    async def get(self, assistant_id: uuid.UUID) -> Assistant | None:
        """Get an assistant configuration by ID."""
        result = await self._session.execute(
            select(Assistant).where(
                Assistant.id == assistant_id,
                Assistant.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        active_only: bool = True,
    ) -> tuple[list[Assistant], int]:
        """List assistant configurations with pagination."""
        base_query = select(Assistant)
        if active_only:
            base_query = base_query.where(Assistant.is_active.is_(True))

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        # Fetch page
        query = base_query.order_by(Assistant.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        assistants = list(result.scalars().all())

        return assistants, total

    async def update(self, assistant_id: uuid.UUID, data: AssistantUpdate) -> Assistant | None:
        """Update an assistant configuration."""
        assistant = await self.get(assistant_id)
        if assistant is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        # Map 'metadata' field to 'metadata_' column
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")

        for field, value in update_data.items():
            setattr(assistant, field, value)

        await self._session.commit()
        await self._session.refresh(assistant)
        return assistant

    async def delete(self, assistant_id: uuid.UUID) -> bool:
        """Soft-delete an assistant configuration (set is_active=False)."""
        assistant = await self.get(assistant_id)
        if assistant is None:
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
    """
    from app.agents.prompts import AGENT_PROMPT_REGISTRY

    svc = AssistantService(session)
    existing = await svc.count(active_only=False)
    if existing > 0:
        logger.debug("Assistants table already has %d rows — skipping seed", existing)
        return

    logger.info("Seeding %d default assistants", len(DEFAULT_ASSISTANTS))
    for entry in DEFAULT_ASSISTANTS:
        agent_type = str(entry["type"])
        registry_entry = AGENT_PROMPT_REGISTRY.get(agent_type, {})
        system_prompt: str | None = registry_entry.get("system_prompt")  # type: ignore[assignment]
        tools: list[str] = registry_entry.get("tools") or []  # type: ignore[assignment]

        data = AssistantCreate(
            name=str(entry["name"]),
            description=str(entry["description"]),
            system_prompt=system_prompt,
            tools_enabled=tools,
            metadata={"agent_type": agent_type, "is_default": True},
        )
        assistant = await svc.create(data)
        logger.info("Seeded assistant %r (id=%s)", assistant.name, assistant.id)

    logger.info("Default assistant seeding complete")
