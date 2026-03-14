"""Agent tools — placeholder for future tool implementations.

Tools such as web_search, knowledge_base, and code_interpreter will be
registered here in subsequent tickets.
"""

from typing import Any

# Tool registry: maps tool name -> tool callable.
# Populated by individual tool modules as they are implemented.
TOOL_REGISTRY: dict[str, Any] = {}

__all__ = ["TOOL_REGISTRY"]
