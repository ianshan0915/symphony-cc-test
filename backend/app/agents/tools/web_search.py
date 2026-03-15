"""Web search tool using the Tavily API.

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

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilySearchError(Exception):
    """Raised when a Tavily API request fails."""


async def _tavily_search(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
) -> dict[str, Any]:
    """Execute a search request against the Tavily API.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results to return (1-10).
    search_depth:
        Either ``"basic"`` (fast) or ``"advanced"`` (thorough).
    include_answer:
        Whether to include a generated answer summary.

    Returns
    -------
    dict
        Raw response from the Tavily API.
    """
    if not settings.tavily_api_key:
        raise TavilySearchError(
            "TAVILY_API_KEY is not configured. Set the tavily_api_key environment variable."
        )

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": min(max_results, 10),
        "search_depth": search_depth,
        "include_answer": include_answer,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(TAVILY_SEARCH_URL, json=payload)

    if response.status_code != 200:
        logger.error("Tavily API error: %s %s", response.status_code, response.text)
        raise TavilySearchError(
            f"Tavily API returned status {response.status_code}: {response.text}"
        )

    result: dict[str, Any] = response.json()
    return result


def _format_results(raw: dict[str, Any]) -> str:
    """Format Tavily API results into a readable string with citations.

    Returns a structured text block the LLM can use to compose a cited answer.
    """
    parts: list[str] = []

    # Include the generated answer summary if available
    answer = raw.get("answer")
    if answer:
        parts.append(f"**Summary:** {answer}\n")

    results = raw.get("results", [])
    if not results:
        return "No web results found for the given query."

    parts.append("**Sources:**\n")
    for idx, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        snippet = result.get("content", "")
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
        max_results: Number of results to return (1-10, default 5).
    """
    try:
        raw = await _tavily_search(query, max_results=max_results)
        return _format_results(raw)
    except TavilySearchError as exc:
        logger.warning("Web search failed: %s", exc)
        return f"Web search error: {exc}"
    except Exception as exc:
        logger.exception("Unexpected error during web search")
        return f"Web search encountered an unexpected error: {exc}"
