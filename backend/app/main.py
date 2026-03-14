"""Symphony backend — FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.threads import router as threads_router
from app.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown hooks."""
    # ----- Startup -----
    # DB engine is lazily initialised by SQLAlchemy on first use.
    # TODO: initialise Redis client
    # TODO: initialise LangGraph agent runtime
    yield
    # ----- Shutdown -----
    await engine.dispose()
    # TODO: close Redis connection


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

# --- Routes ---
app.include_router(health_router)
app.include_router(threads_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Legacy liveness probe (kept for backward compat)."""
    return {"status": "ok"}
