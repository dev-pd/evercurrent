"""Google Drive OAuth install + callback.

Mirrors the Slack pattern in `connectors/slack/install.py`: HMAC-signed
state token over `(org_id, issued_at)`, code exchange via
`oauth2.googleapis.com/token`, and a Fernet-encrypted token blob stored
in `connectors.credentials_secret`. The blob is JSON
`{access_token, refresh_token, expires_at}` so the runtime can refresh
without re-running OAuth.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlencode

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings
from evercurrent.connectors.drive.client import exchange_code_for_tokens
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models

log = structlog.get_logger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
DRIVE_OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/drive.readonly "
    "https://www.googleapis.com/auth/drive.metadata.readonly"
)
STATE_MAX_AGE_SECONDS = 600


class InstallStateError(ValueError):
    """Raised when an OAuth callback presents a missing/invalid `state`."""


@dataclass(frozen=True)
class InstallState:
    """Decoded payload encoded into the OAuth `state` query param."""

    org_id: uuid.UUID
    issued_at: int


def _state_secret(settings: Settings) -> bytes:
    secret = settings.connector_secret_key
    if secret is None:
        raise InstallStateError("connector_secret_key not configured")
    return secret.encode()


def encode_state(org_id: uuid.UUID, *, settings: Settings, now: int | None = None) -> str:
    """Build a signed OAuth state token: base64({org_id, issued_at, sig})."""
    issued_at = now if now is not None else int(time.time())
    body = {"org_id": str(org_id), "iat": issued_at}
    raw = json.dumps(body, separators=(",", ":")).encode()
    sig = hmac.new(_state_secret(settings), raw, sha256).hexdigest()
    return base64.urlsafe_b64encode(raw + b"." + sig.encode()).decode()


def decode_state(
    token: str,
    *,
    settings: Settings,
    now: int | None = None,
) -> InstallState:
    try:
        decoded = base64.urlsafe_b64decode(token.encode())
        raw, sig = decoded.rsplit(b".", 1)
    except (ValueError, binascii.Error) as exc:
        raise InstallStateError("malformed state token") from exc

    expected = hmac.new(_state_secret(settings), raw, sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), sig):
        raise InstallStateError("state signature mismatch")

    payload = json.loads(raw.decode())
    now_ts = now if now is not None else int(time.time())
    issued_at = int(payload["iat"])
    if abs(now_ts - issued_at) > STATE_MAX_AGE_SECONDS:
        raise InstallStateError("state token expired")
    return InstallState(org_id=uuid.UUID(payload["org_id"]), issued_at=issued_at)


def _redirect_uri(settings: Settings) -> str:
    base = settings.webhook_public_url or "http://localhost:8000"
    return f"{base.rstrip('/')}/api/v1/connectors/drive/oauth/callback"


def build_install_url(*, org_id: uuid.UUID, settings: Settings) -> str:
    """Return the Google OAuth consent URL for the given org."""
    if settings.google_client_id is None:
        raise InstallStateError("google_client_id not configured")
    redirect_uri = _redirect_uri(settings)
    state = encode_state(org_id, settings=settings)
    qs = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": DRIVE_OAUTH_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        },
    )
    return f"{GOOGLE_AUTHORIZE_URL}?{qs}"


def _encode_token_blob(
    *,
    access_token: str,
    refresh_token: str | None,
    expires_at: int,
) -> str:
    return json.dumps(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        },
        separators=(",", ":"),
    )


async def exchange_and_persist(
    *,
    session: AsyncSession,
    settings: Settings,
    vault: TokenVault,
    code: str,
    state_token: str,
    installed_by_membership_id: uuid.UUID | None,
    now: int | None = None,
) -> uuid.UUID:
    """Exchange code for tokens, persist connector row, return connector id."""
    if settings.google_client_id is None or settings.google_client_secret is None:
        raise InstallStateError("google oauth secrets not configured")

    state = decode_state(state_token, settings=settings)

    token_resp = await exchange_code_for_tokens(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        code=code,
        redirect_uri=_redirect_uri(settings),
    )

    issued_at = now if now is not None else int(time.time())
    blob = _encode_token_blob(
        access_token=token_resp.access_token,
        refresh_token=token_resp.refresh_token,
        expires_at=issued_at + token_resp.expires_in,
    )
    encrypted = vault.encrypt(blob)

    existing = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.org_id == state.org_id,
                models.Connector.kind == "drive",
            ),
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.credentials_secret = encrypted
        existing.status = "active"
        if installed_by_membership_id is not None:
            existing.installed_by = installed_by_membership_id
        await session.flush()
        log.info("drive.install.refreshed", connector_id=str(existing.id))
        return existing.id

    row = models.Connector(
        org_id=state.org_id,
        kind="drive",
        status="active",
        credentials_secret=encrypted,
        installed_by=installed_by_membership_id,
    )
    session.add(row)
    await session.flush()
    log.info("drive.install.new", connector_id=str(row.id))
    return row.id
