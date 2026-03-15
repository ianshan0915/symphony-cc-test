"""Application configuration via environment variables."""

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
    cors_origins: list[str] = ["http://localhost:3000"]

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

    @property
    def database_url_psycopg(self) -> str:
        """Return a psycopg-compatible connection string.

        LangGraph checkpoint/store backends use ``psycopg`` (not asyncpg),
        so we derive a plain ``postgresql://`` URL from the SQLAlchemy one.
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
