"""Subagent configuration — defines specialist subagents for supervisor delegation.

The deepagents framework supports a ``subagents=`` parameter on
``create_deep_agent()`` that automatically provides a ``task`` tool to the
supervisor agent.  Each subagent configuration specifies the specialist's
name, system prompt, and tool set so the supervisor can delegate work to the
right specialist without manual agent type selection.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.prompts import (
    get_prompt_for_agent_type,
    get_tools_for_agent_type,
)
from app.agents.tools import TOOL_REGISTRY
from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subagent type definitions
# ---------------------------------------------------------------------------

#: Agent types that can serve as subagents.  The ``general`` type is excluded
#: because it is the supervisor itself.
SUBAGENT_TYPES: list[str] = ["researcher", "coder", "writer"]

#: Short descriptions shown to the supervisor agent so it can pick the right
#: subagent for a given task.
SUBAGENT_DESCRIPTIONS: dict[str, str] = {
    "researcher": (
        "Specialist for web research, data gathering, and source citation. "
        "Delegates search-heavy tasks to this subagent for thorough, "
        "well-sourced answers."
    ),
    "coder": (
        "Specialist for code generation, review, debugging, and technical "
        "implementation. Delegates programming tasks to this subagent for "
        "high-quality, well-tested code."
    ),
    "writer": (
        "Specialist for content writing, editing, and document creation. "
        "Delegates writing tasks to this subagent for clear, well-structured "
        "prose."
    ),
}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _resolve_subagent_tools(agent_type: str) -> list[str]:
    """Return tool names for a subagent type.

    Falls back to all registered tool names if the agent type has no
    specific tool list.
    """
    tools = get_tools_for_agent_type(agent_type)
    if tools is not None:
        return tools
    return list(TOOL_REGISTRY.keys())


def build_subagent_configs(
    *,
    model_name: str | None = None,
    model_kwargs: dict[str, Any] | None = None,
    subagent_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build subagent configuration dicts for the deepagents framework.

    Parameters
    ----------
    model_name:
        LLM model identifier for subagents.  Defaults to
        ``settings.default_model``.
    model_kwargs:
        Additional keyword arguments forwarded to each subagent's model.
    subagent_types:
        List of agent type names to create subagents for.  Defaults to
        :data:`SUBAGENT_TYPES` (researcher, coder, writer).

    Returns
    -------
    list[dict[str, Any]]
        A list of subagent config dicts suitable for passing to
        ``create_deep_agent(subagents=...)``.
    """
    types = subagent_types or SUBAGENT_TYPES
    model = model_name or settings.default_model
    configs: list[dict[str, Any]] = []

    for agent_type in types:
        prompt = get_prompt_for_agent_type(agent_type)
        tool_names = _resolve_subagent_tools(agent_type)
        description = SUBAGENT_DESCRIPTIONS.get(agent_type, f"{agent_type} specialist")

        config: dict[str, Any] = {
            "name": agent_type,
            "description": description,
            "model": model,
            "system_prompt": prompt,
            "tools": tool_names,
        }

        if model_kwargs:
            config["model_kwargs"] = model_kwargs

        configs.append(config)
        logger.debug(
            "Subagent config built: name=%s, tools=%d",
            agent_type,
            len(tool_names),
        )

    logger.info("Built %d subagent configurations: %s", len(configs), [c["name"] for c in configs])
    return configs
