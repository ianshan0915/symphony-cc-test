"""Agent tools — tool registry and exports.

Tools such as web_search, knowledge_base, file tools, and code_interpreter
are registered here for use by the agent factory.
"""

from typing import Any

from app.agents.tools.file_tools import (
    create_file,
    delete_file,
    edit_file,
    list_files,
    read_file,
    write_file,
)
from app.agents.tools.knowledge_base import search_knowledge_base
from app.agents.tools.web_search import web_search

# Tool registry: maps tool name -> tool callable.
TOOL_REGISTRY: dict[str, Any] = {
    "web_search": web_search,
    "search_knowledge_base": search_knowledge_base,
    "create_file": create_file,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "list_files": list_files,
}

__all__ = [
    "TOOL_REGISTRY",
    "create_file",
    "delete_file",
    "edit_file",
    "list_files",
    "read_file",
    "search_knowledge_base",
    "web_search",
    "write_file",
]
