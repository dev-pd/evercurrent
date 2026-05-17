"""Application settings, loaded from environment via pydantic-settings.

The same Settings class is used by the FastAPI app and the Celery worker so
both processes converge on a single source of truth for DB / Redis /
LLM credentials. No globals — `get_settings()` is cached and injected.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database + cache
    database_url: str = Field(
        default="postgresql+asyncpg://evercurrent:evercurrent@postgres:5432/evercurrent",
    )
    redis_url: str = Field(default="redis://redis:6379/0")

    # LLM + embeddings
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    voyage_model: str = "voyage-3-lite"
    voyage_embedding_dim: int = 512

    # Logging / observability
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str | None = None

    # Frontend
    next_public_api_url: str = "/api"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
