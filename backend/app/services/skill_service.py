"""Skill service — CRUD operations and materialization for user-created skills."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillCreate, SkillUpdate

logger = logging.getLogger(__name__)


class SkillService:
    """CRUD operations for user-created and system-wide skills."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: SkillCreate, user_id: uuid.UUID) -> Skill:
        """Create a new user skill."""
        skill = Skill(
            user_id=user_id,
            name=data.name,
            description=data.description,
            instructions=data.instructions,
            metadata_=data.metadata,
        )
        self._session.add(skill)
        await self._session.commit()
        await self._session.refresh(skill)
        return skill

    async def get(self, skill_id: uuid.UUID) -> Skill | None:
        """Get a skill by ID (active only)."""
        result = await self._session.execute(
            select(Skill).where(
                Skill.id == skill_id,
                Skill.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Skill], int]:
        """List skills visible to a user: system-wide (user_id=NULL) + user's own.

        Returns (skills, total_count) for pagination.
        """
        base_query = select(Skill).where(
            Skill.is_active.is_(True),
            or_(
                Skill.user_id.is_(None),  # System-wide skills
                Skill.user_id == user_id,  # User's own skills
            ),
        )

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        # Fetch page ordered by creation date (system skills first, then user skills)
        query = (
            base_query.order_by(
                Skill.user_id.is_not(None),  # System skills (NULL user_id) first
                Skill.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        skills = list(result.scalars().all())

        return skills, total

    async def update(
        self, skill_id: uuid.UUID, data: SkillUpdate, user_id: uuid.UUID
    ) -> Skill | None:
        """Update a skill. Users can only edit their own skills."""
        skill = await self.get(skill_id)
        if skill is None:
            return None

        # Ownership check: user can only edit their own skills
        if skill.user_id is None or skill.user_id != user_id:
            return None

        update_data = data.model_dump(exclude_unset=True)
        # Map 'metadata' field to 'metadata_' column
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")

        for field, value in update_data.items():
            setattr(skill, field, value)

        await self._session.commit()
        await self._session.refresh(skill)
        return skill

    async def delete(self, skill_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Soft-delete a skill. Users can only delete their own skills."""
        skill = await self.get(skill_id)
        if skill is None:
            return False

        # Ownership check: user can only delete their own skills
        if skill.user_id is None or skill.user_id != user_id:
            return False

        skill.is_active = False
        await self._session.commit()
        return True

    async def materialize(self, skill_ids: list[uuid.UUID]) -> list[str]:  # type: ignore[valid-type]
        """Materialize skills to temporary filesystem directories for deepagents.

        Creates a temporary directory structure matching the agentskills.io spec:
            temp_dir/
              skill-name/
                SKILL.md   (YAML frontmatter + instructions body)

        Returns a list of absolute paths to the materialized skill directories.
        """
        if not skill_ids:
            return []

        result = await self._session.execute(
            select(Skill).where(
                Skill.id.in_(skill_ids),
                Skill.is_active.is_(True),
            )
        )
        skills = list(result.scalars().all())

        if not skills:
            return []

        # Create a persistent temp directory (caller is responsible for cleanup)
        base_dir = Path(tempfile.mkdtemp(prefix="symphony_skills_"))
        materialized_paths: list[str] = []

        for skill in skills:
            skill_dir = base_dir / skill.name
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Build SKILL.md with YAML frontmatter
            frontmatter = {
                "name": skill.name,
                "description": skill.description,
            }
            if skill.metadata_:
                # Include extra metadata fields (license, compatibility, etc.)
                if "license" in skill.metadata_:
                    frontmatter["license"] = skill.metadata_["license"]
                if "compatibility" in skill.metadata_:
                    frontmatter["compatibility"] = skill.metadata_["compatibility"]

            skill_md_content = "---\n"
            skill_md_content += yaml.dump(frontmatter, default_flow_style=False).strip()
            skill_md_content += "\n---\n\n"
            skill_md_content += skill.instructions

            skill_md_path = skill_dir / "SKILL.md"
            skill_md_path.write_text(skill_md_content, encoding="utf-8")

            materialized_paths.append(str(skill_dir))
            logger.info("Materialized skill '%s' to %s", skill.name, skill_dir)

        logger.info("Materialized %d skill(s) to %s", len(materialized_paths), base_dir)
        return materialized_paths
