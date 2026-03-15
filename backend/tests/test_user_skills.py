"""Tests for user-created skills CRUD endpoints and service (SYM-67).

Covers:
- Skill name validation per agentskills.io spec
- POST /skills — create user skill
- GET /skills — list skills (system-wide + user's own)
- GET /skills/{id} — get skill detail
- PUT /skills/{id} — update (ownership check)
- DELETE /skills/{id} — soft delete (ownership check)
- SkillService.materialize() — write skill folders to temp dir
- Scoping: user skills visible only to creator, system skills visible to all
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillCreate, SkillUpdate, validate_skill_name
from app.models.user import User
from app.services.skill_service import SkillService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SKILL_PAYLOAD = {
    "name": "my-test-skill",
    "description": "A skill for testing purposes.",
    "instructions": "# My Test Skill\n\nFollow these instructions.",
    "metadata": {"author": "tester", "version": "1.0"},
}


# ---------------------------------------------------------------------------
# Name validation tests
# ---------------------------------------------------------------------------


class TestSkillNameValidation:
    """Tests for skill name validation per agentskills.io spec."""

    def test_valid_simple(self) -> None:
        assert validate_skill_name("my-skill") == "my-skill"

    def test_valid_single_word(self) -> None:
        assert validate_skill_name("debugging") == "debugging"

    def test_valid_with_numbers(self) -> None:
        assert validate_skill_name("data-v2") == "data-v2"

    def test_valid_max_length(self) -> None:
        name = "a" + "b" * 62 + "c"  # 64 chars
        assert validate_skill_name(name) == name

    def test_invalid_empty(self) -> None:
        with pytest.raises(ValueError, match="between 1 and 64"):
            validate_skill_name("")

    def test_invalid_too_long(self) -> None:
        with pytest.raises(ValueError, match="between 1 and 64"):
            validate_skill_name("a" * 65)

    def test_invalid_uppercase(self) -> None:
        with pytest.raises(ValueError, match="lowercase"):
            validate_skill_name("My-Skill")

    def test_invalid_starts_with_hyphen(self) -> None:
        with pytest.raises(ValueError, match="start with a lowercase"):
            validate_skill_name("-skill")

    def test_invalid_ends_with_hyphen(self) -> None:
        with pytest.raises(ValueError, match="start with a lowercase"):
            validate_skill_name("skill-")

    def test_invalid_consecutive_hyphens(self) -> None:
        with pytest.raises(ValueError, match="consecutive hyphens"):
            validate_skill_name("my--skill")

    def test_invalid_starts_with_number(self) -> None:
        with pytest.raises(ValueError, match="start with a lowercase"):
            validate_skill_name("1skill")

    def test_invalid_special_chars(self) -> None:
        with pytest.raises(ValueError):
            validate_skill_name("my_skill")


# ---------------------------------------------------------------------------
# Pydantic schema validation tests
# ---------------------------------------------------------------------------


class TestSkillSchemas:
    """Tests for Pydantic skill schemas."""

    def test_create_valid(self) -> None:
        data = SkillCreate(**SKILL_PAYLOAD)
        assert data.name == "my-test-skill"

    def test_create_invalid_name(self) -> None:
        with pytest.raises(ValueError):
            SkillCreate(
                name="INVALID",
                description="desc",
                instructions="body",
            )

    def test_update_allows_partial(self) -> None:
        data = SkillUpdate(description="new desc")
        dump = data.model_dump(exclude_unset=True)
        assert "description" in dump
        assert "name" not in dump

    def test_update_validates_name_if_provided(self) -> None:
        with pytest.raises(ValueError):
            SkillUpdate(name="BAD--NAME")


# ---------------------------------------------------------------------------
# POST /skills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_skill(client: AsyncClient):
    response = await client.post("/skills", json=SKILL_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "my-test-skill"
    assert data["description"] == "A skill for testing purposes."
    assert data["instructions"] == "# My Test Skill\n\nFollow these instructions."
    assert data["is_active"] is True
    assert data["user_id"] is not None
    assert "id" in data


@pytest.mark.asyncio
async def test_create_skill_minimal(client: AsyncClient):
    response = await client.post(
        "/skills",
        json={
            "name": "minimal-skill",
            "description": "Minimal.",
            "instructions": "Do the thing.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "minimal-skill"
    assert data["metadata"] == {}


@pytest.mark.asyncio
async def test_create_skill_invalid_name(client: AsyncClient):
    response = await client.post(
        "/skills",
        json={
            "name": "BAD NAME",
            "description": "desc",
            "instructions": "body",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_skill_missing_instructions(client: AsyncClient):
    response = await client.post(
        "/skills",
        json={"name": "my-skill", "description": "desc"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_skill_name_consecutive_hyphens(client: AsyncClient):
    response = await client.post(
        "/skills",
        json={
            "name": "my--skill",
            "description": "desc",
            "instructions": "body",
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /skills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_skills_empty(client: AsyncClient):
    response = await client.get("/skills")
    assert response.status_code == 200
    data = response.json()
    assert data["skills"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_skills(client: AsyncClient):
    # Create a few skills
    for i in range(3):
        await client.post(
            "/skills",
            json={
                "name": f"skill-{i}a",
                "description": f"Skill {i}",
                "instructions": f"Instructions {i}",
            },
        )

    response = await client.get("/skills")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["skills"]) == 3


@pytest.mark.asyncio
async def test_list_skills_pagination(client: AsyncClient):
    for i in range(5):
        await client.post(
            "/skills",
            json={
                "name": f"paginated-{i}a",
                "description": f"Paginated {i}",
                "instructions": f"Instructions {i}",
            },
        )

    response = await client.get("/skills?offset=0&limit=2")
    data = response.json()
    assert data["total"] == 5
    assert len(data["skills"]) == 2


# ---------------------------------------------------------------------------
# GET /skills/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_skill(client: AsyncClient):
    create_resp = await client.post("/skills", json=SKILL_PAYLOAD)
    skill_id = create_resp.json()["id"]

    response = await client.get(f"/skills/{skill_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "my-test-skill"


@pytest.mark.asyncio
async def test_get_skill_not_found(client: AsyncClient):
    response = await client.get("/skills/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /skills/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_skill(client: AsyncClient):
    create_resp = await client.post("/skills", json=SKILL_PAYLOAD)
    skill_id = create_resp.json()["id"]

    response = await client.put(
        f"/skills/{skill_id}",
        json={"description": "Updated description", "instructions": "New instructions."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated description"
    assert data["instructions"] == "New instructions."
    # Unchanged fields remain the same
    assert data["name"] == "my-test-skill"


@pytest.mark.asyncio
async def test_update_skill_name(client: AsyncClient):
    create_resp = await client.post("/skills", json=SKILL_PAYLOAD)
    skill_id = create_resp.json()["id"]

    response = await client.put(
        f"/skills/{skill_id}",
        json={"name": "renamed-skill"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "renamed-skill"


@pytest.mark.asyncio
async def test_update_skill_invalid_name(client: AsyncClient):
    create_resp = await client.post("/skills", json=SKILL_PAYLOAD)
    skill_id = create_resp.json()["id"]

    response = await client.put(
        f"/skills/{skill_id}",
        json={"name": "BAD--NAME"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_skill_not_found(client: AsyncClient):
    response = await client.put(
        "/skills/00000000-0000-0000-0000-000000000000",
        json={"description": "Nope"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /skills/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_skill(client: AsyncClient):
    create_resp = await client.post("/skills", json=SKILL_PAYLOAD)
    skill_id = create_resp.json()["id"]

    response = await client.delete(f"/skills/{skill_id}")
    assert response.status_code == 204

    # Should not appear in listing anymore
    list_resp = await client.get("/skills")
    names = [s["name"] for s in list_resp.json()["skills"]]
    assert "my-test-skill" not in names


@pytest.mark.asyncio
async def test_delete_skill_not_found(client: AsyncClient):
    response = await client.delete("/skills/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ownership / scoping tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_skill_visible_to_user(db_session: AsyncSession, test_user: User):
    """System-wide skills (user_id=NULL) should be visible to all users."""
    # Create a system skill directly in DB
    system_skill = Skill(
        user_id=None,
        name="system-skill",
        description="A system-wide skill.",
        instructions="System instructions.",
        metadata_={},
    )
    db_session.add(system_skill)
    await db_session.commit()
    await db_session.refresh(system_skill)

    service = SkillService(db_session)
    skills, total = await service.list(test_user.id)
    assert total >= 1
    names = [s.name for s in skills]
    assert "system-skill" in names


@pytest.mark.asyncio
async def test_other_user_skill_not_visible(db_session: AsyncSession, test_user: User):
    """Skills created by another user should not be visible."""
    other_user_id = uuid.uuid4()

    other_skill = Skill(
        user_id=other_user_id,
        name="other-skill",
        description="Another user's skill.",
        instructions="Other instructions.",
        metadata_={},
    )
    db_session.add(other_skill)
    await db_session.commit()

    service = SkillService(db_session)
    skills, _total = await service.list(test_user.id)
    names = [s.name for s in skills]
    assert "other-skill" not in names


@pytest.mark.asyncio
async def test_cannot_update_system_skill(db_session: AsyncSession, test_user: User):
    """Users cannot update system-wide skills."""
    system_skill = Skill(
        user_id=None,
        name="immutable-system",
        description="System skill.",
        instructions="System body.",
        metadata_={},
    )
    db_session.add(system_skill)
    await db_session.commit()
    await db_session.refresh(system_skill)

    service = SkillService(db_session)
    result = await service.update(
        system_skill.id,
        SkillUpdate(description="Hacked"),
        user_id=test_user.id,
    )
    assert result is None


@pytest.mark.asyncio
async def test_cannot_delete_system_skill(db_session: AsyncSession, test_user: User):
    """Users cannot delete system-wide skills."""
    system_skill = Skill(
        user_id=None,
        name="persistent-system",
        description="System skill.",
        instructions="System body.",
        metadata_={},
    )
    db_session.add(system_skill)
    await db_session.commit()
    await db_session.refresh(system_skill)

    service = SkillService(db_session)
    result = await service.delete(system_skill.id, user_id=test_user.id)
    assert result is False


@pytest.mark.asyncio
async def test_cannot_update_other_user_skill(db_session: AsyncSession, test_user: User):
    """Users cannot update skills owned by another user."""
    other_skill = Skill(
        user_id=uuid.uuid4(),
        name="other-owned",
        description="Other user's skill.",
        instructions="Other body.",
        metadata_={},
    )
    db_session.add(other_skill)
    await db_session.commit()
    await db_session.refresh(other_skill)

    service = SkillService(db_session)
    result = await service.update(
        other_skill.id,
        SkillUpdate(description="Hacked"),
        user_id=test_user.id,
    )
    assert result is None


@pytest.mark.asyncio
async def test_cannot_delete_other_user_skill(db_session: AsyncSession, test_user: User):
    """Users cannot delete skills owned by another user."""
    other_skill = Skill(
        user_id=uuid.uuid4(),
        name="other-delete",
        description="Other user's skill.",
        instructions="Other body.",
        metadata_={},
    )
    db_session.add(other_skill)
    await db_session.commit()
    await db_session.refresh(other_skill)

    service = SkillService(db_session)
    result = await service.delete(other_skill.id, user_id=test_user.id)
    assert result is False


# ---------------------------------------------------------------------------
# Materialization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_materialize_skills(db_session: AsyncSession, test_user: User):
    """Materialized skills should produce valid SKILL.md files."""
    import shutil
    from pathlib import Path

    service = SkillService(db_session)

    # Create a skill
    skill = await service.create(
        SkillCreate(
            name="materialize-test",
            description="A skill to materialize.",
            instructions="# Instructions\n\nDo the thing.",
            metadata={"license": "MIT"},
        ),
        user_id=test_user.id,
    )

    # Materialize
    paths = await service.materialize([skill.id])
    assert len(paths) == 1

    skill_dir = Path(paths[0])
    assert skill_dir.is_dir()
    assert skill_dir.name == "materialize-test"

    skill_md = skill_dir / "SKILL.md"
    assert skill_md.is_file()

    content = skill_md.read_text()
    assert "name: materialize-test" in content
    assert "description: A skill to materialize." in content
    assert "# Instructions" in content
    assert "Do the thing." in content

    # Cleanup temp dir
    shutil.rmtree(skill_dir.parent)


@pytest.mark.asyncio
async def test_materialize_empty_list(db_session: AsyncSession):
    """Materializing an empty list should return empty."""
    service = SkillService(db_session)
    paths = await service.materialize([])
    assert paths == []


@pytest.mark.asyncio
async def test_materialize_nonexistent_ids(db_session: AsyncSession):
    """Materializing non-existent IDs should return empty."""
    service = SkillService(db_session)
    paths = await service.materialize([uuid.uuid4()])
    assert paths == []


@pytest.mark.asyncio
async def test_materialize_integrates_with_skill_parser(
    db_session: AsyncSession, test_user: User
):
    """Materialized skills should be parseable by the existing skills module."""
    import shutil
    from pathlib import Path

    from app.agents.skills import discover_skills

    service = SkillService(db_session)

    skill = await service.create(
        SkillCreate(
            name="parseable-skill",
            description="A skill that can be discovered.",
            instructions="# Parseable\n\nThis should work.",
        ),
        user_id=test_user.id,
    )

    paths = await service.materialize([skill.id])
    assert len(paths) == 1

    # The parent of the skill dir should be discoverable
    parent_dir = Path(paths[0]).parent
    discovered = discover_skills(parent_dir)
    assert "parseable-skill" in discovered
    assert discovered["parseable-skill"].description == "A skill that can be discovered."

    shutil.rmtree(parent_dir)
