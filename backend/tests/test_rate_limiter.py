"""Tests for the Redis-based rate limiter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.deps import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter(max_requests=3, window_seconds=60, key_prefix="test_rl")


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.url.path = "/test"
    request.state = MagicMock(spec=[])  # no user_id attribute
    return request


def _make_mock_redis(execute_return=None):
    """Create a mock Redis client with a synchronous pipeline() method."""
    if execute_return is None:
        execute_return = [None, 0, None, None]

    mock_pipe = MagicMock()
    # Pipeline methods are synchronous (chaining), only execute() is async
    mock_pipe.zremrangebyscore.return_value = mock_pipe
    mock_pipe.zcard.return_value = mock_pipe
    mock_pipe.zadd.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute = AsyncMock(return_value=execute_return)

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    return mock_redis, mock_pipe


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_under_limit(limiter, mock_request):
    """Requests under the limit should pass through."""
    mock_redis, _ = _make_mock_redis([None, 1, None, None])  # count=1 < max=3

    with patch("app.api.deps._get_redis", AsyncMock(return_value=mock_redis)):
        await limiter(mock_request)  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_exceeded(limiter, mock_request):
    """Requests over the limit should get 429."""
    mock_redis, _ = _make_mock_redis([None, 3, None, None])  # count=3 >= max=3

    with patch("app.api.deps._get_redis", AsyncMock(return_value=mock_redis)):
        with pytest.raises(HTTPException) as exc_info:
            await limiter(mock_request)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_noop_without_redis(limiter, mock_request):
    """If Redis is unavailable, requests should pass through."""
    with patch("app.api.deps._get_redis", AsyncMock(return_value=None)):
        await limiter(mock_request)  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_handles_redis_error(limiter, mock_request):
    """Redis errors should be caught; request should pass through."""
    mock_redis = MagicMock()
    mock_redis.pipeline.side_effect = ConnectionError("Redis down")

    with patch("app.api.deps._get_redis", AsyncMock(return_value=mock_redis)):
        await limiter(mock_request)  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_uses_user_id_when_available(limiter):
    """Should use user_id from request state when available."""
    mock_redis, mock_pipe = _make_mock_redis([None, 0, None, None])

    request = MagicMock()
    request.state.user_id = "user-123"
    request.url.path = "/test"

    with patch("app.api.deps._get_redis", AsyncMock(return_value=mock_redis)):
        await limiter(request)
        # Verify the key includes user-123
        call_args = mock_pipe.zremrangebyscore.call_args
        assert "user-123" in call_args[0][0]
