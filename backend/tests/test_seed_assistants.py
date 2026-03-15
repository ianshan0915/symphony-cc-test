"""Tests for the default assistant seeding logic."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.assistant_service import (
    DEFAULT_ASSISTANTS,
    AssistantService,
    seed_default_assistants,
)


@pytest.mark.asyncio
async def test_seed_creates_default_assistants(db_session: AsyncSession):
    """Seeding into an empty table should create all default assistants."""
    svc = AssistantService(db_session)

    # Verify table is empty
    assert await svc.count(active_only=False) == 0

    await seed_default_assistants(db_session)

    # All defaults should now exist
    assistants, total = await svc.list(limit=50)
    assert total == len(DEFAULT_ASSISTANTS)

    names = {a.name for a in assistants}
    expected_names = {str(d["name"]) for d in DEFAULT_ASSISTANTS}
    assert names == expected_names

    # Verify metadata contains agent_type and is_default flag
    for a in assistants:
        assert a.metadata_.get("is_default") is True
        assert a.metadata_.get("agent_type") in {"general", "researcher", "coder", "writer"}


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session: AsyncSession):
    """Running seed twice should not duplicate assistants."""
    await seed_default_assistants(db_session)
    await seed_default_assistants(db_session)

    svc = AssistantService(db_session)
    assert await svc.count() == len(DEFAULT_ASSISTANTS)


@pytest.mark.asyncio
async def test_seed_skips_when_assistants_exist(db_session: AsyncSession):
    """If any assistant exists, seeding should be skipped entirely."""
    from app.models.assistant import AssistantCreate

    svc = AssistantService(db_session)
    await svc.create(AssistantCreate(name="Custom Assistant"))

    await seed_default_assistants(db_session)

    # Should only have the one we created manually
    assert await svc.count() == 1


@pytest.mark.asyncio
async def test_seeded_assistants_have_system_prompts(db_session: AsyncSession):
    """Seeded assistants should carry the system prompt from the prompt registry."""
    await seed_default_assistants(db_session)

    svc = AssistantService(db_session)
    assistants, _ = await svc.list(limit=50)

    # At minimum the General Assistant should have a non-empty system prompt
    general = next(a for a in assistants if a.name == "General Assistant")
    assert general.system_prompt is not None
    assert len(general.system_prompt) > 0
