from __future__ import annotations

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict

from evercurrent.config import get_settings
from evercurrent.connectors.slack.crypto import TokenVault


class InstallResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    redirect_url: str


def vault() -> TokenVault:
    settings = get_settings()
    if settings.connector_secret_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="connector_secret_key not configured",
        )
    return TokenVault(settings.connector_secret_key)
