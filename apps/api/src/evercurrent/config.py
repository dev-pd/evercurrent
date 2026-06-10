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

    # Auth0 (Phase 2)
    auth0_domain: str | None = None
    auth0_audience: str = "https://api.evercurrent.local"
    auth0_client_id: str | None = None
    auth0_client_secret: str | None = None
    auth0_webhook_secret: str | None = None

    # Slack (Phase 3)
    slack_client_id: str | None = None
    slack_client_secret: str | None = None
    slack_signing_secret: str | None = None

    # Google Drive (Phase 10)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = (
        "http://localhost:8000/api/v1/connectors/drive/oauth/callback"
    )

    # Dropbox connector
    dropbox_client_id: str | None = None
    dropbox_client_secret: str | None = None
    dropbox_redirect_uri: str = (
        "http://localhost:8080/api/v1/connectors/dropbox/oauth/callback"
    )

    # Webhook public URL (ngrok in dev)
    webhook_public_url: str | None = None

    # Crypto: 32-byte base64 Fernet key used to encrypt connector tokens
    connector_secret_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
