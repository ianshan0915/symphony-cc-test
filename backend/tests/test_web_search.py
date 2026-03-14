"""Tests for the web search tool."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The @tool decorator can replace the module entry in sys.modules.
# Import the actual module object first, before the decorator runs.
_ws_mod_name = "app.agents.tools.web_search"

# Get the real module (may have been replaced in sys.modules by the @tool decorator)
_ws_module = vars(sys.modules.get("app.agents.tools", {})).get(
    "web_search"
) or sys.modules.get(_ws_mod_name)

# Import the symbols we need directly
from app.agents.tools.web_search import (  # noqa: E402
    TavilySearchError,
    _format_results,
    _tavily_search,
    web_search,
)

# ---------------------------------------------------------------------------
# _format_results
# ---------------------------------------------------------------------------


def test_format_results_with_answer_and_sources():
    raw = {
        "answer": "Python is a programming language.",
        "results": [
            {
                "title": "Python.org",
                "url": "https://python.org",
                "content": "Welcome to Python.",
            },
            {
                "title": "Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Python",
                "content": "Python is a high-level language.",
            },
        ],
    }
    formatted = _format_results(raw)
    assert "Python is a programming language" in formatted
    assert "[Python.org](https://python.org)" in formatted
    assert "1." in formatted
    assert "2." in formatted


def test_format_results_no_results():
    raw = {"results": []}
    assert "No web results" in _format_results(raw)


def test_format_results_truncates_long_snippets():
    raw = {
        "results": [
            {
                "title": "Long",
                "url": "https://example.com",
                "content": "x" * 600,
            }
        ],
    }
    formatted = _format_results(raw)
    assert "..." in formatted
    assert len(formatted) < 700


# ---------------------------------------------------------------------------
# _tavily_search — test by calling the function directly with mocked settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tavily_search_missing_api_key():
    mock_settings = MagicMock()
    mock_settings.tavily_api_key = ""

    with patch.object(_tavily_search, "__module__", _ws_mod_name):
        # Patch the settings referenced inside the function's global scope
        original_settings = _tavily_search.__globals__["settings"]
        _tavily_search.__globals__["settings"] = mock_settings
        try:
            with pytest.raises(TavilySearchError, match="not configured"):
                await _tavily_search("test query")
        finally:
            _tavily_search.__globals__["settings"] = original_settings


@pytest.mark.asyncio
async def test_tavily_search_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "answer": "Test answer",
        "results": [{"title": "Test", "url": "https://test.com", "content": "Test content"}],
    }

    mock_settings = MagicMock()
    mock_settings.tavily_api_key = "tvly-test-key"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    original_settings = _tavily_search.__globals__["settings"]
    original_httpx = _tavily_search.__globals__["httpx"]
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    _tavily_search.__globals__["settings"] = mock_settings
    _tavily_search.__globals__["httpx"] = mock_httpx
    try:
        result = await _tavily_search("test query")
        assert result["answer"] == "Test answer"
    finally:
        _tavily_search.__globals__["settings"] = original_settings
        _tavily_search.__globals__["httpx"] = original_httpx


@pytest.mark.asyncio
async def test_tavily_search_api_error():
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_settings = MagicMock()
    mock_settings.tavily_api_key = "tvly-test-key"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    original_settings = _tavily_search.__globals__["settings"]
    original_httpx = _tavily_search.__globals__["httpx"]
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    _tavily_search.__globals__["settings"] = mock_settings
    _tavily_search.__globals__["httpx"] = mock_httpx
    try:
        with pytest.raises(TavilySearchError, match="500"):
            await _tavily_search("test query")
    finally:
        _tavily_search.__globals__["settings"] = original_settings
        _tavily_search.__globals__["httpx"] = original_httpx


# ---------------------------------------------------------------------------
# web_search tool — mock _tavily_search at the function level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_tool_success():
    """Test the web_search tool end-to-end with mocked Tavily API."""
    mock_tavily = AsyncMock(
        return_value={
            "answer": "Answer here",
            "results": [
                {
                    "title": "Source",
                    "url": "https://source.com",
                    "content": "Content here",
                }
            ],
        }
    )
    # The coroutine is stored on the tool; patch its globals
    original = web_search.coroutine.__globals__["_tavily_search"]
    web_search.coroutine.__globals__["_tavily_search"] = mock_tavily
    try:
        result = await web_search.ainvoke({"query": "test", "max_results": 3})
        assert "Answer here" in result
        assert "Source" in result
    finally:
        web_search.coroutine.__globals__["_tavily_search"] = original


@pytest.mark.asyncio
async def test_web_search_tool_error_handling():
    """Test the web_search tool handles errors gracefully."""
    mock_tavily = AsyncMock(side_effect=TavilySearchError("API key invalid"))

    original = web_search.coroutine.__globals__["_tavily_search"]
    web_search.coroutine.__globals__["_tavily_search"] = mock_tavily
    try:
        result = await web_search.ainvoke({"query": "test"})
        assert "error" in result.lower()
    finally:
        web_search.coroutine.__globals__["_tavily_search"] = original
