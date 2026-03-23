"""Application configuration via environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "Symphony"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "info"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database (PostgreSQL + asyncpg) ---
    database_url: str = "postgresql+asyncpg://symphony:symphony_local@localhost:5432/symphony"

    # --- Database connection pool tuning ---
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800  # seconds — recycle connections after 30 min
    db_pool_timeout: int = 30  # seconds — wait for a connection from the pool

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- CORS ---
    # Configurable via CORS_ORIGINS env var (comma-separated).
    # Example: CORS_ORIGINS=http://localhost:3000,https://app.example.com
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Accept a comma-separated string or a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- LLM / LangChain ---
    openai_api_key: str = ""
    openai_base_url: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    default_model: str = "gpt-4o"

    # --- LangSmith Observability ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "symphony"
    langchain_endpoint: str = ""
    langsmith_tracing: bool = False
    langsmith_endpoint: str = ""

    # --- Brave Web Search ---
    brave_api_key: str = ""

    # --- JWT Authentication ---
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # --- Rate Limiting ---
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # --- Summarization / long-conversation support ---
    # SummarizationMiddleware is auto-included by deepagents with model-aware defaults
    # (fraction-based for profiled models, fixed-token for others). The settings below
    # document our *intended* thresholds and are passed as an explicit additional
    # middleware layer so behaviour is visible, logged, and tunable without touching
    # the deepagents internals.
    #
    # trigger_fraction: fraction of the model's context window that activates summarization.
    #   E.g. 0.85 → summarise when 85 % of context is used.
    # trigger_messages: message-count fallback trigger for models whose context window
    #   size is not known (complements the fraction-based trigger).
    # keep_messages: number of the most-recent messages to preserve verbatim after
    #   summarisation.  Older messages are compressed into a summary.
    # summary_prompt: optional custom prompt for the summarisation LLM call.
    #   Leave empty to use the deepagents default.
    summarization_trigger_fraction: float = 0.85
    summarization_trigger_messages: int = 200
    summarization_keep_messages: int = 20
    summarization_summary_prompt: str = ""

    # --- Sandbox Backend (code execution) ---
    # Controls which sandbox backend provides the ``execute`` tool for running
    # shell commands in isolated environments.
    #
    # LOCAL_SHELL — LocalShellBackend for local development (no true isolation).
    # MODAL / DAYTONA / RUNLOOP — Cloud sandbox providers for production.
    # NONE — Disable code execution; agents cannot run shell commands.
    sandbox_backend: str = "LOCAL_SHELL"

    # Root directory used by LocalShellBackend.  All file-system operations and
    # executed commands run relative to this directory.  An absolute path is
    # required so the directory resolves consistently regardless of the server's
    # current working directory (which can vary across deployment environments).
    sandbox_workspace_dir: str = "/tmp/sandbox_workspace"

    # Extra environment variables injected into sandbox processes.
    # Parsed from a JSON object: e.g. '{"PATH": "/usr/bin:/bin"}'
    sandbox_env: dict[str, str] = {}

    # Whether the sandbox inherits the parent process environment.
    # Enable with caution in production — it may expose host secrets.
    sandbox_inherit_env: bool = False

    # Default timeout (seconds) for sandbox command execution.
    sandbox_timeout: int = 120

    # Maximum byte length of stdout + stderr captured from a command.
    sandbox_max_output_bytes: int = 102_400  # 100 KiB

    @field_validator("sandbox_backend")
    @classmethod
    def validate_sandbox_backend(cls, v: str) -> str:
        """Reject unknown SANDBOX_BACKEND values at startup rather than at first use."""
        _valid = {"NONE", "LOCAL_SHELL", "MODAL", "DAYTONA", "RUNLOOP"}
        if v.upper().strip() not in _valid:
            raise ValueError(
                f"Invalid SANDBOX_BACKEND '{v}'. Valid values: {', '.join(sorted(_valid))}"
            )
        return v

    @property
    def database_url_psycopg(self) -> str:
        """Return a psycopg-compatible connection string.

        LangGraph checkpoint/store backends use ``psycopg`` (not asyncpg),
        so we derive a plain ``postgresql://`` URL from the SQLAlchemy one.
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
