"""Agent tools registry.

Each tool module registers itself here so the agent factory can discover
available tools by name.
"""

from typing import Any

from app.agents.tools.web_search import web_search

# Tool registry: maps tool name -> tool callable.
TOOL_REGISTRY: dict[str, Any] = {
    "web_search": web_search,
}

__all__ = ["TOOL_REGISTRY", "web_search"]
