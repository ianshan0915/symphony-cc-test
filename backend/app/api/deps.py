"""FastAPI dependency injection providers."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_factory
from app.models.user import TokenPayload, User
from app.services.assistant_service import AssistantService
from app.services.thread_service import ThreadService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT containing the user ID and expiration."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": str(user_id), "exp": expire}
    token: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT, returning the payload."""
    try:
        raw = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return TokenPayload(**raw)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

# Always use auto_error=False so auth behaviour is determined at runtime
# (inside get_current_user) rather than at import time.  Previously,
# auto_error was set to ``not settings.debug`` at module level, which meant
# DEBUG=true permanently disabled the 401 response for missing tokens.
_bearer_scheme = HTTPBearer(auto_error=False)

# Stable UUID for the synthetic dev user so references stay consistent.
_DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, closing it when the request ends."""
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Authentication dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Validate the Bearer token and return the authenticated User.

    When ``settings.debug`` is True and no token is provided, returns (or
    creates) a synthetic dev user so the frontend can work without auth.

    Raises 401 if the token is invalid, expired, or the user no longer exists.
    """
    if credentials is None and settings.debug:
        # Return an in-memory dev user for local development (no DB required)
        user = User(
            id=_DEV_USER_ID,
            email="dev@localhost",
            hashed_password="",
            created_at=datetime.now(timezone.utc),
        )
        logger.debug("Using synthetic dev user (debug mode)")
        return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = uuid.UUID(payload.sub)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await session.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return db_user


# ---------------------------------------------------------------------------
# Request-state enrichment (for rate limiting by user)
# ---------------------------------------------------------------------------


async def set_request_user_id(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    """Copy the authenticated user's ID onto ``request.state`` so downstream
    dependencies (e.g. :class:`RateLimiter`) can key limits per-user."""
    request.state.user_id = str(user.id)


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


async def _get_redis() -> Any:
    """Lazily initialise and return the async Redis client."""
    global _redis_client
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
        client = request.client
        user_id = getattr(request.state, "user_id", None) or (client.host if client else "unknown")
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
