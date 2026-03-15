"""Symphony backend — FastAPI application entry point."""

import logging
import sys
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import timezone
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.agents.middleware import setup_persistent_backends, teardown_persistent_backends
from app.api.routes.assistants import router as assistants_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.threads import router as threads_router
from app.config import settings
from app.db.session import engine
from app.services.agent_service import agent_service

# ---------------------------------------------------------------------------
# Request ID context variable (propagated through the entire request lifecycle)
# ---------------------------------------------------------------------------

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Includes timestamp, level, logger name, message, and the current
    request_id from the context variable so every log line within a
    request can be correlated.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get("-"),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def _configure_logging() -> None:
    """Replace the root logger's handlers with a structured JSON handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Quieten noisy third-party loggers
    for name in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


_configure_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown hooks."""
    # ----- Startup -----
    logger.info("Starting Symphony API v%s", settings.app_version)
    await setup_persistent_backends()
    _ = agent_service.agent
    yield
    # ----- Shutdown -----
    logger.info("Shutting down Symphony API")
    await teardown_persistent_backends()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Coroutine[Any, Any, Response]],
) -> Response:
    """Inject a unique request ID into every request/response cycle.

    * Reads ``X-Request-ID`` from the incoming headers (to support
      propagation from upstream proxies/gateways).  If absent, generates
      a new UUID4.
    * Stores the ID in a :class:`~contextvars.ContextVar` so it is
      available in every log line emitted during the request.
    * Returns the ID in the ``X-Request-ID`` response header.
    """
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_ctx.set(rid)
    request.state.request_id = rid

    logger.info(
        "Incoming %s %s",
        request.method,
        request.url.path,
    )

    try:
        response: Response = await call_next(request)
    finally:
        request_id_ctx.reset(token)

    response.headers["X-Request-ID"] = rid
    return response


# --- Routes ---
app.include_router(health_router)
app.include_router(threads_router)
app.include_router(chat_router)
app.include_router(assistants_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Legacy liveness probe (kept for backward compat)."""
    return {"status": "ok"}
