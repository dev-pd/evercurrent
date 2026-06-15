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

    database_url: str = Field(
        default="postgresql+asyncpg://evercurrent:evercurrent@postgres:5432/evercurrent",
    )
    app_database_url: str | None = Field(default=None)
    redis_url: str = Field(default="redis://redis:6379/0")

    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    voyage_model: str = "voyage-3-lite"
    voyage_embedding_dim: int = 512

    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str | None = None

    next_public_api_url: str = "/api"
    app_base_url: str = "http://localhost:8080"

    auth0_domain: str | None = None
    auth0_audience: str = "https://api.evercurrent.local"
    auth0_client_id: str | None = None
    auth0_client_secret: str | None = None
    auth0_webhook_secret: str | None = None

    slack_client_id: str | None = None
    slack_client_secret: str | None = None
    slack_signing_secret: str | None = None
    slack_app_bot_name: str = "EverCurrent"
    slack_demo_bot_token: str | None = None
    slack_workspace_domain: str | None = None

    demo_chatter_enabled: bool = False
    demo_chatter_batch: int = 2
    demo_chatter_phase: str = "fcs"

    dropbox_client_id: str | None = None
    dropbox_client_secret: str | None = None
    dropbox_redirect_uri: str = "http://localhost:8080/api/v1/connectors/dropbox/oauth/callback"

    webhook_public_url: str | None = None

    connector_secret_key: str | None = None

    eve_min_confidence: float = 0.55
    eve_min_grounded_sources: int = 1
    eve_max_insights_per_day: int = 25
    eve_dedup_threshold: float = 0.82


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
