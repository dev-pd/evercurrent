"""Slack OAuth install + callback.

State token contains org_id + a timestamp + an HMAC signed with our
own webhook secret. We use the same `connector_secret_key` as the
token vault, hashed once with HMAC-SHA256 — separate-key separation
isn't worth the take-home cost.
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
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.connectors.slack.schemas import SlackOAuthResponse
from evercurrent.db import models

log = structlog.get_logger(__name__)

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_BOT_SCOPES = "channels:history,groups:history,chat:write,users:read,team:read"
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


def build_install_url(*, org_id: uuid.UUID, settings: Settings) -> str:
    """Return the Slack OAuth consent URL for the given org."""
    if settings.slack_client_id is None:
        raise InstallStateError("slack_client_id not configured")
    redirect_uri = _redirect_uri(settings)
    state = encode_state(org_id, settings=settings)
    qs = urlencode(
        {
            "client_id": settings.slack_client_id,
            "scope": SLACK_BOT_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
        },
    )
    return f"{SLACK_AUTHORIZE_URL}?{qs}"


def _redirect_uri(settings: Settings) -> str:
    base = settings.webhook_public_url or "http://localhost:8000"
    return f"{base.rstrip('/')}/api/v1/connectors/slack/oauth/callback"


async def exchange_and_persist(
    *,
    session: AsyncSession,
    settings: Settings,
    vault: TokenVault,
    code: str,
    state_token: str,
    installed_by_membership_id: uuid.UUID | None,
    slack_client: SlackClient | None = None,
) -> uuid.UUID:
    """Exchange code for tokens, persist connector row, return connector id."""
    if settings.slack_client_id is None or settings.slack_client_secret is None:
        raise InstallStateError("slack oauth secrets not configured")

    state = decode_state(state_token, settings=settings)

    owns_client = slack_client is None
    client = slack_client or SlackClient()
    try:
        oauth_resp: SlackOAuthResponse = await client.oauth_v2_access(
            client_id=settings.slack_client_id,
            client_secret=settings.slack_client_secret,
            code=code,
            redirect_uri=_redirect_uri(settings),
        )
    finally:
        if owns_client:
            await client.aclose()

    if not oauth_resp.ok or oauth_resp.access_token is None or oauth_resp.team is None:
        raise InstallStateError(f"oauth exchange failed: {oauth_resp.error or 'unknown'}")

    team_id = oauth_resp.team.get("id")
    if team_id is None:
        raise InstallStateError("oauth response missing team.id")
    encrypted = vault.encrypt(oauth_resp.access_token)

    existing = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.org_id == state.org_id,
                models.Connector.kind == "slack",
            ),
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.credentials_secret = encrypted
        existing.external_team_id = team_id
        existing.status = "active"
        if installed_by_membership_id is not None:
            existing.installed_by = installed_by_membership_id
        await session.flush()
        log.info("slack.install.refreshed", connector_id=str(existing.id))
        return existing.id

    row = models.Connector(
        org_id=state.org_id,
        kind="slack",
        status="active",
        external_team_id=team_id,
        credentials_secret=encrypted,
        installed_by=installed_by_membership_id,
    )
    session.add(row)
    await session.flush()
    log.info("slack.install.new", connector_id=str(row.id))
    return row.id
