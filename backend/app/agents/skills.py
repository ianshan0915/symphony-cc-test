"""Agent Skills loader — discovers, parses, and activates skills per the agentskills.io spec.

Skills are folders containing ``SKILL.md`` files with YAML frontmatter (name + description)
and Markdown instruction bodies. They follow progressive disclosure:

1. **Discovery** — only ``name`` + ``description`` loaded at startup (~100 tokens/skill)
2. **Activation** — full ``SKILL.md`` body loaded when task matches
3. **Execution** — agent follows instructions, loads referenced scripts/assets as needed
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill data model
# ---------------------------------------------------------------------------

# Default system-wide skills directory (relative to backend/)
_SYSTEM_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


@dataclass(frozen=True)
class SkillMetadata:
    """Tier-1 metadata loaded at discovery time (~50-100 tokens per skill)."""

    name: str
    description: str
    location: Path  # Absolute path to SKILL.md
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)

    @property
    def base_dir(self) -> Path:
        """Return the skill directory (parent of SKILL.md)."""
        return self.location.parent


@dataclass
class ActivatedSkill:
    """Tier-2 data: full instructions loaded when skill is activated."""

    meta: SkillMetadata
    body: str  # Markdown instruction body (frontmatter stripped)
    resources: list[str] = field(default_factory=list)  # Relative paths to bundled files


# ---------------------------------------------------------------------------
# SKILL.md parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)

# Name validation per agentskills.io spec
_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def _validate_name(name: str) -> bool:
    """Validate a skill name per the agentskills.io specification."""
    if not name or len(name) > 64:
        return False
    if "--" in name:
        return False
    return bool(_NAME_RE.match(name))


def parse_skill_md(skill_md_path: Path) -> SkillMetadata | None:
    """Parse a SKILL.md file and return tier-1 metadata.

    Returns ``None`` if the file cannot be parsed or is missing a description.
    Applies lenient validation per the agentskills.io client implementation guide.
    """
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Cannot read %s: %s", skill_md_path, exc)
        return None

    match = _FRONTMATTER_RE.match(content)
    if not match:
        logger.error("No YAML frontmatter found in %s", skill_md_path)
        return None

    yaml_block = match.group(1)
    try:
        fm: dict[str, Any] = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        # Fallback: try wrapping description value in quotes (common cross-client issue)
        try:
            fixed = re.sub(
                r"^(description:\s*)(.+)$",
                lambda m: m.group(1) + '"' + m.group(2).replace('"', '\\"') + '"',
                yaml_block,
                flags=re.MULTILINE,
            )
            fm = yaml.safe_load(fixed) or {}
        except yaml.YAMLError as exc:
            logger.error("Unparseable YAML in %s: %s", skill_md_path, exc)
            return None

    name = str(fm.get("name", ""))
    description = str(fm.get("description", ""))

    if not description.strip():
        logger.error("Skill %s has no description — skipping", skill_md_path)
        return None

    # Lenient validation: warn but still load
    if not _validate_name(name):
        logger.warning(
            "Skill name '%s' in %s does not match spec — loading anyway",
            name,
            skill_md_path,
        )

    parent_dir_name = skill_md_path.parent.name
    if name and name != parent_dir_name:
        logger.warning(
            "Skill name '%s' does not match directory '%s' — loading anyway",
            name,
            parent_dir_name,
        )

    # Parse optional fields
    skill_license = fm.get("license")
    compatibility = fm.get("compatibility")
    skill_metadata = fm.get("metadata") or {}
    allowed_tools_raw = fm.get("allowed-tools", "")
    allowed_tools = allowed_tools_raw.split() if isinstance(allowed_tools_raw, str) else []

    return SkillMetadata(
        name=name or parent_dir_name,
        description=description,
        location=skill_md_path.resolve(),
        license=str(skill_license) if skill_license else None,
        compatibility=str(compatibility) if compatibility else None,
        metadata={str(k): str(v) for k, v in skill_metadata.items()} if skill_metadata else {},
        allowed_tools=allowed_tools,
    )


# ---------------------------------------------------------------------------
# Discovery — scan directories for skills
# ---------------------------------------------------------------------------

# Directories to skip during scanning
_SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", ".tox"})


def discover_skills(
    *skill_dirs: str | Path,
    max_depth: int = 4,
) -> dict[str, SkillMetadata]:
    """Discover all skills in the given directories.

    Scans each directory for subdirectories containing ``SKILL.md`` files.
    Returns a dict keyed by skill name. Later directories take precedence
    (project-level overrides system-level).

    Parameters
    ----------
    skill_dirs:
        Directories to scan for skill subdirectories. Non-existent paths
        are silently skipped.
    max_depth:
        Maximum directory depth to scan (default 4).
    """
    skills: dict[str, SkillMetadata] = {}

    for base_dir in skill_dirs:
        base = Path(base_dir)
        if not base.is_dir():
            logger.debug("Skill directory does not exist: %s", base)
            continue

        _scan_dir(base, skills, current_depth=0, max_depth=max_depth)

    logger.info("Discovered %d skill(s): %s", len(skills), ", ".join(skills.keys()) or "(none)")
    return skills


def _scan_dir(
    directory: Path,
    skills: dict[str, SkillMetadata],
    current_depth: int,
    max_depth: int,
) -> None:
    """Recursively scan a directory for SKILL.md files."""
    if current_depth > max_depth:
        return

    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return

    for entry in entries:
        if not entry.is_dir() or entry.name in _SKIP_DIRS:
            continue

        skill_md = entry / "SKILL.md"
        if skill_md.is_file():
            meta = parse_skill_md(skill_md)
            if meta is not None:
                if meta.name in skills:
                    logger.warning(
                        "Skill '%s' from %s shadows previous definition at %s",
                        meta.name,
                        meta.location,
                        skills[meta.name].location,
                    )
                skills[meta.name] = meta
        else:
            # Recurse into subdirectory
            _scan_dir(entry, skills, current_depth + 1, max_depth)


# ---------------------------------------------------------------------------
# Activation — load full instructions (tier 2)
# ---------------------------------------------------------------------------


def activate_skill(meta: SkillMetadata) -> ActivatedSkill:
    """Activate a skill by loading its full SKILL.md body and enumerating resources.

    This is tier-2 of progressive disclosure — the full instruction body is loaded
    on demand when the agent determines the skill is relevant.
    """
    content = meta.location.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    body = match.group(2).strip() if match else content.strip()

    # Enumerate bundled resources (scripts/, references/, assets/)
    resources: list[str] = []
    for subdir_name in ("scripts", "references", "assets"):
        subdir = meta.base_dir / subdir_name
        if subdir.is_dir():
            for root, _dirs, files in os.walk(subdir):
                for fname in sorted(files):
                    rel = os.path.relpath(os.path.join(root, fname), meta.base_dir)
                    resources.append(rel)

    return ActivatedSkill(meta=meta, body=body, resources=resources)


# ---------------------------------------------------------------------------
# Skill catalog — XML format for system prompt injection
# ---------------------------------------------------------------------------


def build_skill_catalog(skills: dict[str, SkillMetadata]) -> str:
    """Build an XML skill catalog string for system prompt injection.

    This is the tier-1 disclosure: only name + description (~50-100 tokens/skill).
    """
    if not skills:
        return ""

    lines = ["<available_skills>"]
    for meta in skills.values():
        lines.append("  <skill>")
        lines.append(f"    <name>{meta.name}</name>")
        lines.append(f"    <description>{meta.description}</description>")
        lines.append(f"    <location>{meta.location}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def format_activated_skill(activated: ActivatedSkill) -> str:
    """Format an activated skill's content for injection into context.

    Wraps the skill body in structured XML tags per the agentskills.io
    client implementation guide.
    """
    parts = [f'<skill_content name="{activated.meta.name}">']
    parts.append(activated.body)
    parts.append("")
    parts.append(f"Skill directory: {activated.meta.base_dir}")
    parts.append("Relative paths in this skill are relative to the skill directory.")

    if activated.resources:
        parts.append("")
        parts.append("<skill_resources>")
        for res in activated.resources:
            parts.append(f"  <file>{res}</file>")
        parts.append("</skill_resources>")

    parts.append("</skill_content>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Skill resolution for agent types
# ---------------------------------------------------------------------------

# Maps agent types to the skill names they should have access to.
# None means "all available skills".
AGENT_TYPE_SKILLS: dict[str, list[str] | None] = {
    "general": None,
    "researcher": ["web-research", "data-analysis"],
    "coder": ["code-review", "debugging"],
    "writer": ["content-writing", "editing"],
}


def get_skills_for_agent_type(agent_type: str | None) -> list[str] | None:
    """Return the skill names recommended for a given agent type.

    Returns ``None`` for unknown types or ``"general"`` (meaning all skills).
    """
    if not agent_type:
        return None
    return AGENT_TYPE_SKILLS.get(agent_type)


def resolve_skill_paths(
    skills: list[str] | None = None,
    assistant_type: str | None = None,
    extra_skill_dirs: list[str | Path] | None = None,
) -> list[str]:
    """Resolve skill directory paths for agent creation.

    Priority:
    1. Explicitly provided ``skills`` list (skill names).
    2. Skill names from the agent type's recommended list.
    3. All discovered skills (fallback).

    Parameters
    ----------
    skills:
        Explicit skill names to load.
    assistant_type:
        Agent specialization type — used to filter skills.
    extra_skill_dirs:
        Additional directories to scan for skills beyond the system dir.

    Returns
    -------
    list[str]
        Absolute paths to skill directories.
    """
    dirs: list[str | Path] = [_SYSTEM_SKILLS_DIR]
    if extra_skill_dirs:
        dirs.extend(extra_skill_dirs)

    discovered = discover_skills(*dirs)

    if not discovered:
        return []

    # Determine which skill names to include
    if skills is not None:
        # Explicit skill names provided
        requested = set(skills)
    elif assistant_type:
        type_skills = get_skills_for_agent_type(assistant_type)
        requested = set(type_skills) if type_skills is not None else set(discovered.keys())
    else:
        requested = set(discovered.keys())

    # Resolve to paths
    paths: list[str] = []
    for name in requested:
        if name in discovered:
            paths.append(str(discovered[name].base_dir))
        else:
            logger.warning("Requested skill '%s' not found in discovered skills", name)

    return paths


# ---------------------------------------------------------------------------
# System skills directory accessor
# ---------------------------------------------------------------------------


def get_system_skills_dir() -> Path:
    """Return the path to the system-wide skills directory."""
    return _SYSTEM_SKILLS_DIR
