"""Agent tools — tool registry and exports.

Tools such as web_search, knowledge_base, and code_interpreter are
registered here for use by the agent factory.
"""

from typing import Any

from app.agents.tools.knowledge_base import search_knowledge_base
from app.agents.tools.web_search import web_search

# Tool registry: maps tool name -> tool callable.
TOOL_REGISTRY: dict[str, Any] = {
    "web_search": web_search,
    "search_knowledge_base": search_knowledge_base,
}

__all__ = ["TOOL_REGISTRY", "web_search", "search_knowledge_base"]
