"""Web search tool using the Brave Search API.

Allows the agent to search the web for current information and return
results with source citations.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchError(Exception):
    """Raised when a Brave Search API request fails."""


async def _brave_search(
    query: str,
    *,
    max_results: int = 5,
) -> dict[str, Any]:
    """Execute a search request against the Brave Search API.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results to return (1-20).

    Returns
    -------
    dict
        Raw response from the Brave Search API.
    """
    if not settings.brave_api_key:
        raise BraveSearchError(
            "BRAVE_API_KEY is not configured. Set the brave_api_key environment variable."
        )

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_api_key,
    }

    params: dict[str, str | int] = {
        "q": query,
        "count": min(max_results, 20),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(BRAVE_SEARCH_URL, headers=headers, params=params)

    if response.status_code != 200:
        logger.error("Brave Search API error: %s %s", response.status_code, response.text)
        raise BraveSearchError(
            f"Brave Search API returned status {response.status_code}: {response.text}"
        )

    result: dict[str, Any] = response.json()
    return result


def _format_results(raw: dict[str, Any]) -> str:
    """Format Brave Search API results into a readable string with citations.

    Returns a structured text block the LLM can use to compose a cited answer.
    """
    parts: list[str] = []

    web = raw.get("web", {})
    results = web.get("results", [])
    if not results:
        return "No web results found for the given query."

    parts.append("**Sources:**\n")
    for idx, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        snippet = result.get("description", "")
        # Truncate long snippets
        if len(snippet) > 500:
            snippet = snippet[:497] + "..."
        parts.append(f"{idx}. [{title}]({url})\n   {snippet}\n")

    return "\n".join(parts)


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information on a topic.

    Use this tool when you need up-to-date information, facts, news, or
    data that may not be in your training data.  Returns results with
    source URLs for citation.

    Args:
        query: The search query string describing what to look up.
        max_results: Number of results to return (1-20, default 5).
    """
    try:
        raw = await _brave_search(query, max_results=max_results)
        return _format_results(raw)
    except BraveSearchError as exc:
        logger.warning("Web search failed: %s", exc)
        return f"Web search error: {exc}"
    except Exception as exc:
        logger.exception("Unexpected error during web search")
        return f"Web search encountered an unexpected error: {exc}"
