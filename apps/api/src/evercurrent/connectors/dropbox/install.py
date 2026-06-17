"""Dropbox OAuth install flow: signed state encode/decode and building the install URL."""

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
from evercurrent.connectors.dropbox.client import exchange_code_for_tokens
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models

log = structlog.get_logger(__name__)

DROPBOX_AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"
STATE_MAX_AGE_SECONDS = 600


class InstallStateError(ValueError):
    pass


@dataclass(frozen=True)
class InstallState:
    org_id: uuid.UUID
    issued_at: int


def _state_secret(settings: Settings) -> bytes:
    secret = settings.connector_secret_key
    if secret is None:
        raise InstallStateError("connector_secret_key not configured")
    return secret.encode()


def encode_state(org_id: uuid.UUID, *, settings: Settings, now: int | None = None) -> str:
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
    return settings.dropbox_redirect_uri


def build_install_url(*, org_id: uuid.UUID, settings: Settings) -> str:
    if settings.dropbox_client_id is None:
        raise InstallStateError("dropbox_client_id not configured")
    state = encode_state(org_id, settings=settings)
    qs = urlencode(
        {
            "client_id": settings.dropbox_client_id,
            "redirect_uri": _redirect_uri(settings),
            "response_type": "code",
            "token_access_type": "offline",
            "scope": "account_info.read files.metadata.read files.content.read",
            "state": state,
        },
    )
    return f"{DROPBOX_AUTHORIZE_URL}?{qs}"


def _encode_token_blob(
    *,
    access_token: str,
    refresh_token: str | None,
    expires_at: int,
    account_id: str,
) -> str:
    return json.dumps(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "account_id": account_id,
        },
        separators=(",", ":"),
    )


def decode_token_blob(plaintext: str) -> dict[str, object]:
    return json.loads(plaintext)


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
    if settings.dropbox_client_id is None or settings.dropbox_client_secret is None:
        raise InstallStateError("dropbox oauth secrets not configured")

    state = decode_state(state_token, settings=settings)

    token_resp = await exchange_code_for_tokens(
        code=code,
        client_id=settings.dropbox_client_id,
        client_secret=settings.dropbox_client_secret,
        redirect_uri=_redirect_uri(settings),
    )

    issued_at = now if now is not None else int(time.time())
    blob = _encode_token_blob(
        access_token=token_resp.access_token,
        refresh_token=token_resp.refresh_token,
        expires_at=issued_at + token_resp.expires_in,
        account_id=token_resp.account_id,
    )
    encrypted = vault.encrypt(blob)

    existing = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.org_id == state.org_id,
                models.Connector.kind == "dropbox",
            ),
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.credentials_secret = encrypted
        existing.status = "active"
        existing.external_team_id = token_resp.account_id
        if installed_by_membership_id is not None:
            existing.installed_by = installed_by_membership_id
        await session.flush()
        log.info("dropbox.install.refreshed", connector_id=str(existing.id))
        return existing.id

    row = models.Connector(
        id=uuid.uuid4(),
        org_id=state.org_id,
        kind="dropbox",
        status="active",
        external_team_id=token_resp.account_id,
        credentials_secret=encrypted,
        installed_by=installed_by_membership_id,
    )
    session.add(row)
    await session.flush()
    log.info("dropbox.install.new", connector_id=str(row.id))
    return row.id
