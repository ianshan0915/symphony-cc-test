"""FastAPI dependency injection providers."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_factory
from app.services.assistant_service import AssistantService
from app.services.thread_service import ThreadService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, closing it when the request ends."""
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Service providers
# ---------------------------------------------------------------------------


async def get_thread_service(
    session: AsyncSession = Depends(get_db_session),
) -> ThreadService:
    """Return a ThreadService backed by the request-scoped DB session."""
    return ThreadService(session)


async def get_assistant_service(
    session: AsyncSession = Depends(get_db_session),
) -> AssistantService:
    """Return an AssistantService backed by the request-scoped DB session."""
    return AssistantService(session)


# ---------------------------------------------------------------------------
# Redis-based rate limiting
# ---------------------------------------------------------------------------

_redis_client = None


async def _get_redis():
    """Lazily initialise and return the async Redis client."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        try:
            from redis.asyncio import Redis

            _redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        except Exception:
            logger.warning("Redis unavailable — rate limiting disabled")
            return None
    return _redis_client


class RateLimiter:
    """Sliding-window rate limiter backed by Redis.

    Falls back to no-op when Redis is unavailable so the application
    remains functional (but unprotected).

    Parameters
    ----------
    max_requests:
        Maximum number of requests allowed within the window.
    window_seconds:
        Length of the sliding window in seconds.
    key_prefix:
        Prefix for the Redis key (allows per-endpoint limiting).
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
        key_prefix: str = "rl",
    ) -> None:
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds
        self.key_prefix = key_prefix

    async def __call__(self, request: Request) -> None:
        """FastAPI dependency — raises 429 if the rate limit is exceeded."""
        redis = await _get_redis()
        if redis is None:
            return  # No Redis → rate limiting disabled

        # Identify user: prefer authenticated user id, fall back to IP
        user_id = getattr(request.state, "user_id", None) or request.client.host
        endpoint = request.url.path
        key = f"{self.key_prefix}:{user_id}:{endpoint}"

        now = time.time()
        window_start = now - self.window_seconds

        try:
            pipe = redis.pipeline()
            # Remove entries outside the current window
            pipe.zremrangebyscore(key, 0, window_start)
            # Count remaining entries
            pipe.zcard(key)
            # Add the current request
            pipe.zadd(key, {str(now): now})
            # Set expiry on the key
            pipe.expire(key, self.window_seconds)
            results = await pipe.execute()

            request_count = results[1]

            if request_count >= self.max_requests:
                logger.info(
                    "Rate limit exceeded for user=%s endpoint=%s (%d/%d)",
                    user_id,
                    endpoint,
                    request_count,
                    self.max_requests,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Max {self.max_requests} requests "
                    f"per {self.window_seconds}s.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("Rate limiter Redis error — allowing request", exc_info=True)


# Pre-configured rate limiter instances
rate_limiter = RateLimiter()
rate_limiter_strict = RateLimiter(max_requests=10, window_seconds=60, key_prefix="rl_strict")
