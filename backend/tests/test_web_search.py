"""Tests for the web search tool."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The @tool decorator can replace the module entry in sys.modules.
# Import the actual module object first, before the decorator runs.
_ws_mod_name = "app.agents.tools.web_search"

# Get the real module (may have been replaced in sys.modules by the @tool decorator)
_ws_module = vars(sys.modules.get("app.agents.tools", {})).get("web_search") or sys.modules.get(
    _ws_mod_name
)

# Import the symbols we need directly
from app.agents.tools.web_search import (  # noqa: E402
    BraveSearchError,
    _brave_search,
    _format_results,
    web_search,
)

# ---------------------------------------------------------------------------
# _format_results
# ---------------------------------------------------------------------------


def test_format_results_with_sources():
    raw = {
        "web": {
            "results": [
                {
                    "title": "Python.org",
                    "url": "https://python.org",
                    "description": "Welcome to Python.",
                },
                {
                    "title": "Wikipedia",
                    "url": "https://en.wikipedia.org/wiki/Python",
                    "description": "Python is a high-level language.",
                },
            ],
        },
    }
    formatted = _format_results(raw)
    assert "[Python.org](https://python.org)" in formatted
    assert "1." in formatted
    assert "2." in formatted


def test_format_results_no_results():
    raw = {"web": {"results": []}}
    assert "No web results" in _format_results(raw)


def test_format_results_truncates_long_snippets():
    raw = {
        "web": {
            "results": [
                {
                    "title": "Long",
                    "url": "https://example.com",
                    "description": "x" * 600,
                }
            ],
        },
    }
    formatted = _format_results(raw)
    assert "..." in formatted
    assert len(formatted) < 700


# ---------------------------------------------------------------------------
# _brave_search — test by calling the function directly with mocked settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brave_search_missing_api_key():
    mock_settings = MagicMock()
    mock_settings.brave_api_key = ""

    with patch.object(_brave_search, "__module__", _ws_mod_name):
        # Patch the settings referenced inside the function's global scope
        original_settings = _brave_search.__globals__["settings"]
        _brave_search.__globals__["settings"] = mock_settings
        try:
            with pytest.raises(BraveSearchError, match="not configured"):
                await _brave_search("test query")
        finally:
            _brave_search.__globals__["settings"] = original_settings


@pytest.mark.asyncio
async def test_brave_search_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "Test", "url": "https://test.com", "description": "Test content"}
            ],
        },
    }

    mock_settings = MagicMock()
    mock_settings.brave_api_key = "BSA-test-key"

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    original_settings = _brave_search.__globals__["settings"]
    original_httpx = _brave_search.__globals__["httpx"]
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    _brave_search.__globals__["settings"] = mock_settings
    _brave_search.__globals__["httpx"] = mock_httpx
    try:
        result = await _brave_search("test query")
        assert result["web"]["results"][0]["title"] == "Test"
    finally:
        _brave_search.__globals__["settings"] = original_settings
        _brave_search.__globals__["httpx"] = original_httpx


@pytest.mark.asyncio
async def test_brave_search_api_error():
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_settings = MagicMock()
    mock_settings.brave_api_key = "BSA-test-key"

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    original_settings = _brave_search.__globals__["settings"]
    original_httpx = _brave_search.__globals__["httpx"]
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    _brave_search.__globals__["settings"] = mock_settings
    _brave_search.__globals__["httpx"] = mock_httpx
    try:
        with pytest.raises(BraveSearchError, match="500"):
            await _brave_search("test query")
    finally:
        _brave_search.__globals__["settings"] = original_settings
        _brave_search.__globals__["httpx"] = original_httpx


# ---------------------------------------------------------------------------
# web_search tool — mock _brave_search at the function level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_tool_success():
    """Test the web_search tool end-to-end with mocked Brave Search API."""
    mock_brave = AsyncMock(
        return_value={
            "web": {
                "results": [
                    {
                        "title": "Source",
                        "url": "https://source.com",
                        "description": "Content here",
                    }
                ],
            },
        }
    )
    # The coroutine is stored on the tool; patch its globals
    original = web_search.coroutine.__globals__["_brave_search"]
    web_search.coroutine.__globals__["_brave_search"] = mock_brave
    try:
        result = await web_search.ainvoke({"query": "test", "max_results": 3})
        assert "Source" in result
    finally:
        web_search.coroutine.__globals__["_brave_search"] = original


@pytest.mark.asyncio
async def test_web_search_tool_error_handling():
    """Test the web_search tool handles errors gracefully."""
    mock_brave = AsyncMock(side_effect=BraveSearchError("API key invalid"))

    original = web_search.coroutine.__globals__["_brave_search"]
    web_search.coroutine.__globals__["_brave_search"] = mock_brave
    try:
        result = await web_search.ainvoke({"query": "test"})
        assert "error" in result.lower()
    finally:
        web_search.coroutine.__globals__["_brave_search"] = original
