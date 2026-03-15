"""Tests for Agent Skills support (SYM-66).

Covers:
- SKILL.md parsing (frontmatter extraction, validation, edge cases)
- Skill discovery (directory scanning, name collisions, skip dirs)
- Skill activation (body extraction, resource enumeration)
- Skill catalog generation (XML format)
- Skill resolution by agent type
- Factory integration with skills parameter
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.prompts import get_skills_for_agent_type
from app.agents.skills import (
    AGENT_TYPE_SKILLS,
    ActivatedSkill,
    SkillMetadata,
    _validate_name,
    activate_skill,
    build_skill_catalog,
    discover_skills,
    format_activated_skill,
    get_system_skills_dir,
    parse_skill_md,
    resolve_skill_paths,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with test skills."""
    # Skill 1: valid skill with all optional dirs
    skill1 = tmp_path / "test-skill"
    skill1.mkdir()
    (skill1 / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill for unit testing purposes.\n"
        "license: MIT\n"
        "metadata:\n"
        "  author: test\n"
        "  version: '1.0'\n"
        "---\n"
        "# Test Skill\n\n"
        "## Instructions\n\n"
        "Follow these steps to test things.\n"
    )
    scripts = skill1 / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text("print('hello')\n")
    refs = skill1 / "references"
    refs.mkdir()
    (refs / "REFERENCE.md").write_text("# Reference\n\nSome reference material.\n")

    # Skill 2: minimal valid skill
    skill2 = tmp_path / "minimal-skill"
    skill2.mkdir()
    (skill2 / "SKILL.md").write_text(
        "---\n"
        "name: minimal-skill\n"
        "description: A minimal skill with no optional directories.\n"
        "---\n"
    )

    return tmp_path


@pytest.fixture()
def malformed_skills_dir(tmp_path: Path) -> Path:
    """Create a directory with malformed SKILL.md files."""
    # No frontmatter
    bad1 = tmp_path / "no-frontmatter"
    bad1.mkdir()
    (bad1 / "SKILL.md").write_text("# Just markdown\n\nNo frontmatter here.\n")

    # No description
    bad2 = tmp_path / "no-description"
    bad2.mkdir()
    (bad2 / "SKILL.md").write_text("---\nname: no-description\n---\n# Content\n")

    # Completely invalid YAML
    bad3 = tmp_path / "bad-yaml"
    bad3.mkdir()
    (bad3 / "SKILL.md").write_text("---\n: : :\n  [\n---\n# Content\n")

    return tmp_path


# ---------------------------------------------------------------------------
# Name validation tests
# ---------------------------------------------------------------------------


class TestNameValidation:
    """Tests for skill name validation per agentskills.io spec."""

    def test_valid_simple_name(self) -> None:
        assert _validate_name("pdf-processing") is True

    def test_valid_single_word(self) -> None:
        assert _validate_name("debugging") is True

    def test_valid_with_numbers(self) -> None:
        assert _validate_name("data-analysis-v2") is True

    def test_invalid_empty(self) -> None:
        assert _validate_name("") is False

    def test_invalid_uppercase(self) -> None:
        assert _validate_name("PDF-Processing") is False

    def test_invalid_starts_with_hyphen(self) -> None:
        assert _validate_name("-pdf") is False

    def test_invalid_ends_with_hyphen(self) -> None:
        assert _validate_name("pdf-") is False

    def test_invalid_consecutive_hyphens(self) -> None:
        assert _validate_name("pdf--processing") is False

    def test_invalid_too_long(self) -> None:
        assert _validate_name("a" * 65) is False

    def test_valid_max_length(self) -> None:
        assert _validate_name("a" * 64) is True


# ---------------------------------------------------------------------------
# SKILL.md parsing tests
# ---------------------------------------------------------------------------


class TestParseSkillMd:
    """Tests for SKILL.md frontmatter and body parsing."""

    def test_parse_full_skill(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        assert meta.name == "test-skill"
        assert "test skill" in meta.description.lower()
        assert meta.license == "MIT"
        assert meta.metadata.get("author") == "test"

    def test_parse_minimal_skill(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "minimal-skill" / "SKILL.md")
        assert meta is not None
        assert meta.name == "minimal-skill"
        assert meta.license is None
        assert meta.metadata == {}

    def test_parse_no_frontmatter_returns_none(self, malformed_skills_dir: Path) -> None:
        meta = parse_skill_md(malformed_skills_dir / "no-frontmatter" / "SKILL.md")
        assert meta is None

    def test_parse_no_description_returns_none(self, malformed_skills_dir: Path) -> None:
        meta = parse_skill_md(malformed_skills_dir / "no-description" / "SKILL.md")
        assert meta is None

    def test_parse_bad_yaml_returns_none(self, malformed_skills_dir: Path) -> None:
        meta = parse_skill_md(malformed_skills_dir / "bad-yaml" / "SKILL.md")
        assert meta is None

    def test_parse_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        meta = parse_skill_md(tmp_path / "nonexistent" / "SKILL.md")
        assert meta is None

    def test_location_is_absolute(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        assert meta.location.is_absolute()

    def test_base_dir_is_skill_directory(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        assert meta.base_dir.name == "test-skill"

    def test_name_mismatch_warns_but_loads(self, tmp_path: Path) -> None:
        """Lenient validation: name mismatch should warn but still load."""
        skill_dir = tmp_path / "actual-dir-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: different-name\n"
            "description: Name does not match directory.\n"
            "---\n"
        )
        meta = parse_skill_md(skill_dir / "SKILL.md")
        assert meta is not None
        assert meta.name == "different-name"

    def test_allowed_tools_parsed(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "with-tools"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: with-tools\n"
            "description: Skill with allowed tools.\n"
            "allowed-tools: Bash Read Write\n"
            "---\n"
        )
        meta = parse_skill_md(skill_dir / "SKILL.md")
        assert meta is not None
        assert meta.allowed_tools == ["Bash", "Read", "Write"]

    def test_compatibility_field(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "compat-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: compat-skill\n"
            "description: Skill with compatibility.\n"
            "compatibility: Requires Python 3.11+\n"
            "---\n"
        )
        meta = parse_skill_md(skill_dir / "SKILL.md")
        assert meta is not None
        assert meta.compatibility == "Requires Python 3.11+"

    def test_yaml_with_unquoted_colon_fallback(self, tmp_path: Path) -> None:
        """Common cross-client issue: unquoted colons in description."""
        skill_dir = tmp_path / "colon-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: colon-skill\n"
            "description: Use when: the user asks about colons\n"
            "---\n"
        )
        # Should either parse or fallback — not crash
        # The specific behavior depends on whether YAML accepts this
        parse_skill_md(skill_dir / "SKILL.md")


# ---------------------------------------------------------------------------
# Discovery tests
# ---------------------------------------------------------------------------


class TestDiscoverSkills:
    """Tests for skill directory scanning and discovery."""

    def test_discover_finds_valid_skills(self, tmp_skills_dir: Path) -> None:
        skills = discover_skills(tmp_skills_dir)
        assert "test-skill" in skills
        assert "minimal-skill" in skills
        assert len(skills) == 2

    def test_discover_skips_malformed(self, malformed_skills_dir: Path) -> None:
        skills = discover_skills(malformed_skills_dir)
        assert len(skills) == 0

    def test_discover_nonexistent_dir(self, tmp_path: Path) -> None:
        skills = discover_skills(tmp_path / "nonexistent")
        assert len(skills) == 0

    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        skills = discover_skills(empty)
        assert len(skills) == 0

    def test_discover_multiple_dirs(self, tmp_skills_dir: Path, tmp_path: Path) -> None:
        """Skills from multiple directories are merged."""
        extra = tmp_path / "extra"
        extra.mkdir()
        extra_skill = extra / "extra-skill"
        extra_skill.mkdir()
        (extra_skill / "SKILL.md").write_text(
            "---\nname: extra-skill\ndescription: An extra skill.\n---\n"
        )

        skills = discover_skills(tmp_skills_dir, extra)
        assert "test-skill" in skills
        assert "extra-skill" in skills

    def test_discover_later_dir_overrides(self, tmp_path: Path) -> None:
        """Skills in later directories shadow earlier ones (project > system)."""
        dir1 = tmp_path / "system"
        dir1.mkdir()
        s1 = dir1 / "my-skill"
        s1.mkdir()
        (s1 / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: System version.\n---\n"
        )

        dir2 = tmp_path / "project"
        dir2.mkdir()
        s2 = dir2 / "my-skill"
        s2.mkdir()
        (s2 / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: Project version.\n---\n"
        )

        skills = discover_skills(dir1, dir2)
        assert skills["my-skill"].description == "Project version."

    def test_discover_skips_git_dirs(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        skill_in_git = git_dir / "hidden-skill"
        skill_in_git.mkdir()
        (skill_in_git / "SKILL.md").write_text(
            "---\nname: hidden-skill\ndescription: Should not be found.\n---\n"
        )
        skills = discover_skills(tmp_path)
        assert "hidden-skill" not in skills

    def test_discover_respects_max_depth(self, tmp_path: Path) -> None:
        # Create a deeply nested skill
        deep = tmp_path
        for i in range(6):
            deep = deep / f"level{i}"
            deep.mkdir()
        skill = deep / "deep-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: deep-skill\ndescription: Very deep.\n---\n"
        )

        # Default max_depth=4 should not find it
        skills = discover_skills(tmp_path, max_depth=4)
        assert "deep-skill" not in skills

        # But higher depth should
        skills = discover_skills(tmp_path, max_depth=10)
        assert "deep-skill" in skills


# ---------------------------------------------------------------------------
# Activation tests
# ---------------------------------------------------------------------------


class TestActivateSkill:
    """Tests for skill activation (tier 2 — full body loading)."""

    def test_activate_returns_body(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        assert "# Test Skill" in activated.body
        assert "Follow these steps" in activated.body

    def test_activate_strips_frontmatter(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        assert "---" not in activated.body
        assert "name:" not in activated.body

    def test_activate_enumerates_resources(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        assert any("scripts/helper.py" in r for r in activated.resources)
        assert any("references/REFERENCE.md" in r for r in activated.resources)

    def test_activate_minimal_has_no_resources(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "minimal-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        assert activated.resources == []

    def test_activate_body_is_empty_for_metadata_only_skill(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "meta-only"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: meta-only\ndescription: Only metadata.\n---\n"
        )
        meta = parse_skill_md(skill_dir / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        assert activated.body == ""


# ---------------------------------------------------------------------------
# Catalog generation tests
# ---------------------------------------------------------------------------


class TestBuildSkillCatalog:
    """Tests for XML skill catalog generation."""

    def test_catalog_contains_all_skills(self, tmp_skills_dir: Path) -> None:
        skills = discover_skills(tmp_skills_dir)
        catalog = build_skill_catalog(skills)
        assert "<available_skills>" in catalog
        assert "test-skill" in catalog
        assert "minimal-skill" in catalog
        assert "</available_skills>" in catalog

    def test_catalog_includes_description(self, tmp_skills_dir: Path) -> None:
        skills = discover_skills(tmp_skills_dir)
        catalog = build_skill_catalog(skills)
        assert "A test skill for unit testing purposes." in catalog

    def test_catalog_includes_location(self, tmp_skills_dir: Path) -> None:
        skills = discover_skills(tmp_skills_dir)
        catalog = build_skill_catalog(skills)
        assert "<location>" in catalog
        assert "SKILL.md" in catalog

    def test_empty_catalog_returns_empty_string(self) -> None:
        assert build_skill_catalog({}) == ""


# ---------------------------------------------------------------------------
# Formatted activated skill tests
# ---------------------------------------------------------------------------


class TestFormatActivatedSkill:
    """Tests for structured XML wrapping of activated skills."""

    def test_format_wraps_in_xml_tags(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        formatted = format_activated_skill(activated)
        assert '<skill_content name="test-skill">' in formatted
        assert "</skill_content>" in formatted

    def test_format_includes_skill_directory(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        formatted = format_activated_skill(activated)
        assert "Skill directory:" in formatted

    def test_format_includes_resources(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "test-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        formatted = format_activated_skill(activated)
        assert "<skill_resources>" in formatted
        assert "scripts/helper.py" in formatted

    def test_format_omits_resources_when_empty(self, tmp_skills_dir: Path) -> None:
        meta = parse_skill_md(tmp_skills_dir / "minimal-skill" / "SKILL.md")
        assert meta is not None
        activated = activate_skill(meta)
        formatted = format_activated_skill(activated)
        assert "<skill_resources>" not in formatted


# ---------------------------------------------------------------------------
# System skills directory tests
# ---------------------------------------------------------------------------


class TestSystemSkills:
    """Tests for the system-wide skills directory."""

    def test_system_skills_dir_exists(self) -> None:
        skills_dir = get_system_skills_dir()
        assert skills_dir.is_dir(), f"System skills directory does not exist: {skills_dir}"

    def test_system_skills_are_discoverable(self) -> None:
        skills = discover_skills(get_system_skills_dir())
        assert len(skills) > 0, "No system skills found"

    def test_system_skills_include_expected_skills(self) -> None:
        skills = discover_skills(get_system_skills_dir())
        expected = {"web-research", "data-analysis", "code-review", "debugging",
                    "content-writing", "editing"}
        found = set(skills.keys())
        assert expected.issubset(found), f"Missing skills: {expected - found}"

    def test_all_system_skills_have_valid_metadata(self) -> None:
        skills = discover_skills(get_system_skills_dir())
        for name, meta in skills.items():
            assert meta.name, f"Skill {name} has no name"
            assert meta.description, f"Skill {name} has no description"
            assert meta.location.is_file(), f"Skill {name} SKILL.md not found"

    def test_all_system_skills_can_be_activated(self) -> None:
        skills = discover_skills(get_system_skills_dir())
        for name, meta in skills.items():
            activated = activate_skill(meta)
            assert isinstance(activated, ActivatedSkill)
            # Body should be non-empty for real skills
            assert len(activated.body) > 0, f"Skill {name} has empty body"


# ---------------------------------------------------------------------------
# Agent type skill resolution tests
# ---------------------------------------------------------------------------


class TestAgentTypeSkills:
    """Tests for skill resolution by agent type."""

    def test_general_type_skills_is_none(self) -> None:
        assert AGENT_TYPE_SKILLS["general"] is None

    def test_researcher_has_research_skills(self) -> None:
        skills = AGENT_TYPE_SKILLS["researcher"]
        assert skills is not None
        assert "web-research" in skills
        assert "data-analysis" in skills

    def test_coder_has_coding_skills(self) -> None:
        skills = AGENT_TYPE_SKILLS["coder"]
        assert skills is not None
        assert "code-review" in skills
        assert "debugging" in skills

    def test_writer_has_writing_skills(self) -> None:
        skills = AGENT_TYPE_SKILLS["writer"]
        assert skills is not None
        assert "content-writing" in skills
        assert "editing" in skills

    def test_prompts_registry_skills_match(self) -> None:
        """Skills in prompts registry should match AGENT_TYPE_SKILLS."""
        assert get_skills_for_agent_type("general") is None
        assert get_skills_for_agent_type("researcher") == ["web-research", "data-analysis"]
        assert get_skills_for_agent_type("coder") == ["code-review", "debugging"]
        assert get_skills_for_agent_type("writer") == ["content-writing", "editing"]

    def test_unknown_type_returns_none(self) -> None:
        assert get_skills_for_agent_type("nonexistent") is None


# ---------------------------------------------------------------------------
# Skill path resolution tests
# ---------------------------------------------------------------------------


class TestResolveSkillPaths:
    """Tests for resolve_skill_paths()."""

    def test_explicit_skills_resolved(self, tmp_skills_dir: Path) -> None:
        paths = resolve_skill_paths(
            skills=["test-skill"],
            extra_skill_dirs=[str(tmp_skills_dir)],
        )
        assert len(paths) == 1
        assert "test-skill" in paths[0]

    def test_assistant_type_resolves_skills(self) -> None:
        """Researcher type should resolve web-research and data-analysis."""
        paths = resolve_skill_paths(assistant_type="researcher")
        # These should come from the system skills dir
        assert len(paths) == 2

    def test_general_type_gets_all_skills(self) -> None:
        paths = resolve_skill_paths(assistant_type="general")
        assert len(paths) >= 6  # All system skills

    def test_missing_skill_warns_and_skips(self, tmp_skills_dir: Path) -> None:
        paths = resolve_skill_paths(
            skills=["nonexistent-skill"],
            extra_skill_dirs=[str(tmp_skills_dir)],
        )
        assert len(paths) == 0

    def test_no_args_returns_all(self) -> None:
        paths = resolve_skill_paths()
        assert len(paths) >= 6  # All system skills


# ---------------------------------------------------------------------------
# Factory integration tests
# ---------------------------------------------------------------------------


class TestFactoryWithSkills:
    """Tests for create_deep_agent with skills parameter."""

    @staticmethod
    def _import_factory():
        from app.agents.factory import create_deep_agent

        return create_deep_agent

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_agent_with_explicit_skills(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        create_deep_agent = self._import_factory()
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(skills=["web-research", "code-review"])
        assert agent is not None
        mock_da_create.assert_called_once()

        call_kwargs = mock_da_create.call_args
        assert "skills" in call_kwargs.kwargs
        assert len(call_kwargs.kwargs["skills"]) == 2

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_researcher_gets_research_skills(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        create_deep_agent = self._import_factory()
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(assistant_type="researcher")
        assert agent is not None
        mock_da_create.assert_called_once()

        call_kwargs = mock_da_create.call_args
        assert "skills" in call_kwargs.kwargs
        skill_paths = call_kwargs.kwargs["skills"]
        # Should have 2 skills: web-research and data-analysis
        assert len(skill_paths) == 2

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_agent_no_skills_omits_param(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        """When no skills are resolved (empty list), skills param is omitted."""
        create_deep_agent = self._import_factory()
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        with patch("app.agents.factory.resolve_skill_paths", return_value=[]):
            agent = create_deep_agent()
            assert agent is not None
            call_kwargs = mock_da_create.call_args
            assert "skills" not in call_kwargs.kwargs

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_agent_with_extra_skill_dirs(
        self, mock_model: MagicMock, mock_da_create: MagicMock, tmp_skills_dir: Path
    ) -> None:
        create_deep_agent = self._import_factory()
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(
            skills=["test-skill"],
            extra_skill_dirs=[str(tmp_skills_dir)],
        )
        assert agent is not None
        call_kwargs = mock_da_create.call_args
        assert "skills" in call_kwargs.kwargs

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_coder_gets_coding_skills(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        create_deep_agent = self._import_factory()
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(assistant_type="coder")
        assert agent is not None
        call_kwargs = mock_da_create.call_args
        assert "skills" in call_kwargs.kwargs
        assert len(call_kwargs.kwargs["skills"]) == 2

    @patch("app.agents.factory._deepagents_create")
    @patch("app.agents.factory._get_chat_model")
    def test_create_writer_gets_writing_skills(
        self, mock_model: MagicMock, mock_da_create: MagicMock
    ) -> None:
        create_deep_agent = self._import_factory()
        mock_model.return_value = MagicMock()
        mock_da_create.return_value = MagicMock()

        agent = create_deep_agent(assistant_type="writer")
        assert agent is not None
        call_kwargs = mock_da_create.call_args
        assert "skills" in call_kwargs.kwargs
        assert len(call_kwargs.kwargs["skills"]) == 2


# ---------------------------------------------------------------------------
# SkillMetadata dataclass tests
# ---------------------------------------------------------------------------


class TestSkillMetadata:
    """Tests for the SkillMetadata dataclass."""

    def test_frozen(self) -> None:
        meta = SkillMetadata(
            name="test",
            description="A test.",
            location=Path("/tmp/test/SKILL.md"),
        )
        with pytest.raises(AttributeError):
            meta.name = "changed"  # type: ignore[misc]

    def test_base_dir(self) -> None:
        meta = SkillMetadata(
            name="test",
            description="A test.",
            location=Path("/tmp/test/SKILL.md"),
        )
        assert meta.base_dir == Path("/tmp/test")

    def test_defaults(self) -> None:
        meta = SkillMetadata(
            name="test",
            description="A test.",
            location=Path("/tmp/test/SKILL.md"),
        )
        assert meta.license is None
        assert meta.compatibility is None
        assert meta.metadata == {}
        assert meta.allowed_tools == []
