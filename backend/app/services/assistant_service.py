"""Assistant configuration service — CRUD operations for assistant configs."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantCreate, AssistantUpdate


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

    async def update(
        self, assistant_id: uuid.UUID, data: AssistantUpdate
    ) -> Assistant | None:
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
