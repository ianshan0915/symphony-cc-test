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
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/symphony"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- LLM / LangChain ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_model: str = "gpt-4o"

    # --- LangSmith Observability ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "symphony"

    # --- Tavily Web Search ---
    tavily_api_key: str = ""

    # --- Rate Limiting ---
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60


settings = Settings()
