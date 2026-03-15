"""Agent prompt templates — general and specialized agent prompts.

Each agent type has a distinct system prompt and recommended tool configuration.
Use ``get_prompt_for_agent_type`` to resolve a prompt by assistant type, or
``AGENT_PROMPT_REGISTRY`` for direct access to the full registry.
"""

from __future__ import annotations

from typing import Any

from app.agents.prompts.coder import CODER_SYSTEM_PROMPT, CODER_TOOLS
from app.agents.prompts.general import GENERAL_SYSTEM_PROMPT
from app.agents.prompts.researcher import RESEARCHER_SYSTEM_PROMPT, RESEARCHER_TOOLS
from app.agents.prompts.writer import WRITER_SYSTEM_PROMPT, WRITER_TOOLS

# ---------------------------------------------------------------------------
# Agent type registry — maps assistant type names to (prompt, tools) pairs
# ---------------------------------------------------------------------------

AGENT_PROMPT_REGISTRY: dict[str, dict[str, Any]] = {
    "general": {
        "system_prompt": GENERAL_SYSTEM_PROMPT,
        "tools": None,  # None means "use all available tools"
        "skills": None,  # None means "use all available skills"
    },
    "researcher": {
        "system_prompt": RESEARCHER_SYSTEM_PROMPT,
        "tools": RESEARCHER_TOOLS,
        "skills": ["web-research", "data-analysis"],
    },
    "coder": {
        "system_prompt": CODER_SYSTEM_PROMPT,
        "tools": CODER_TOOLS,
        "skills": ["code-review", "debugging"],
    },
    "writer": {
        "system_prompt": WRITER_SYSTEM_PROMPT,
        "tools": WRITER_TOOLS,
        "skills": ["content-writing", "editing"],
    },
}

# Valid agent type names (for validation)
VALID_AGENT_TYPES: set[str] = set(AGENT_PROMPT_REGISTRY.keys())


def get_prompt_for_agent_type(agent_type: str) -> str:
    """Return the system prompt for the given agent type.

    Falls back to the general-purpose prompt for unknown types.
    """
    entry = AGENT_PROMPT_REGISTRY.get(agent_type)
    if entry is None:
        return GENERAL_SYSTEM_PROMPT
    return str(entry["system_prompt"])


def get_tools_for_agent_type(agent_type: str) -> list[str] | None:
    """Return the recommended tool names for the given agent type.

    Returns ``None`` for unknown types or ``"general"`` (meaning all tools).
    """
    entry = AGENT_PROMPT_REGISTRY.get(agent_type)
    if entry is None:
        return None
    tools: list[str] | None = entry["tools"]
    return tools


def get_skills_for_agent_type(agent_type: str) -> list[str] | None:
    """Return the recommended skill names for the given agent type.

    Returns ``None`` for unknown types or ``"general"`` (meaning all skills).
    """
    entry = AGENT_PROMPT_REGISTRY.get(agent_type)
    if entry is None:
        return None
    skills: list[str] | None = entry.get("skills")
    return skills


__all__ = [
    "AGENT_PROMPT_REGISTRY",
    "CODER_SYSTEM_PROMPT",
    "CODER_TOOLS",
    "GENERAL_SYSTEM_PROMPT",
    "RESEARCHER_SYSTEM_PROMPT",
    "RESEARCHER_TOOLS",
    "VALID_AGENT_TYPES",
    "WRITER_SYSTEM_PROMPT",
    "WRITER_TOOLS",
    "get_prompt_for_agent_type",
    "get_skills_for_agent_type",
    "get_tools_for_agent_type",
]
