"""Drive push-notification channel registration + renewal.

`register_watch(folder_id, connector_id)` calls `files.watch` against a
folder with our public webhook URL, a freshly minted channel token, and
a 7-day expiry. The (channel_id, channel_token, resource_id, expires_at)
tuple is persisted as JSON in `connector_channels.name` for take-home
simplicity — production would split this into its own column set.

`renew_drive_watches()` runs daily on Celery Beat at 02:00 UTC. It looks
for channels expiring inside 36 hours and re-registers them. The 36h
buffer means even one missed cron run leaves recovery room.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import uuid
from dataclasses import dataclass
from secrets import token_urlsafe

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings, get_settings
from evercurrent.connectors.drive.client import DriveClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.db.session import session_scope

log = structlog.get_logger(__name__)

WATCH_TTL_SECONDS = 7 * 24 * 60 * 60
RENEW_BUFFER_SECONDS = 36 * 60 * 60


@dataclass(frozen=True)
class WatchRecord:
    """The bookkeeping we persist for each registered Drive watch channel."""

    channel_id: str
    channel_token: str
    resource_id: str
    folder_id: str
    expires_at: int


def encode_watch_metadata(record: WatchRecord) -> str:
    return json.dumps(
        {
            "channel_id": record.channel_id,
            "channel_token": record.channel_token,
            "resource_id": record.resource_id,
            "folder_id": record.folder_id,
            "expires_at": record.expires_at,
        },
        separators=(",", ":"),
    )


def decode_watch_metadata(blob: str) -> WatchRecord | None:
    try:
        data = json.loads(blob)
    except (ValueError, TypeError):
        return None
    required = ("channel_id", "channel_token", "resource_id", "folder_id", "expires_at")
    if not all(k in data for k in required):
        return None
    return WatchRecord(
        channel_id=str(data["channel_id"]),
        channel_token=str(data["channel_token"]),
        resource_id=str(data["resource_id"]),
        folder_id=str(data["folder_id"]),
        expires_at=int(data["expires_at"]),
    )


def _webhook_url(settings: Settings) -> str:
    base = settings.webhook_public_url or "http://localhost:8000"
    return f"{base.rstrip('/')}/api/v1/webhooks/drive"


async def register_watch(
    *,
    session: AsyncSession,
    settings: Settings,
    drive_client: DriveClient,
    connector_id: uuid.UUID,
    folder_id: str,
    folder_name: str | None = None,
    now: int | None = None,
) -> WatchRecord:
    """Register or refresh a push channel for `folder_id`.

    Persists a `connector_channels` row keyed by `(connector_id, folder_id)`
    with the channel bookkeeping JSON-encoded in `name` for take-home
    simplicity — production would split into dedicated columns.
    """
    channel_id = str(uuid.uuid4())
    channel_token = token_urlsafe(32)
    webhook_url = _webhook_url(settings)
    resp = await drive_client.files_watch(
        file_id=folder_id,
        channel_id=channel_id,
        channel_token=channel_token,
        webhook_url=webhook_url,
        ttl_seconds=WATCH_TTL_SECONDS,
    )
    issued_at = now if now is not None else int(time.time())
    if resp.expiration is not None:
        # Google returns expiration as ms-since-epoch.
        expires_at = resp.expiration // 1000
    else:
        expires_at = issued_at + WATCH_TTL_SECONDS

    record = WatchRecord(
        channel_id=channel_id,
        channel_token=channel_token,
        resource_id=resp.resource_id,
        folder_id=folder_id,
        expires_at=expires_at,
    )

    existing = (
        await session.execute(
            select(models.ConnectorChannel).where(
                models.ConnectorChannel.connector_id == connector_id,
                models.ConnectorChannel.external_id == folder_id,
            ),
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.name = encode_watch_metadata(record)
        existing.ingest = True
    else:
        connector = await session.get(models.Connector, connector_id)
        if connector is None:
            msg = f"connector {connector_id!s} not found"
            raise ValueError(msg)
        session.add(
            models.ConnectorChannel(
                org_id=connector.org_id,
                connector_id=connector_id,
                external_id=folder_id,
                name=folder_name or encode_watch_metadata(record),
                ingest=True,
            ),
        )
    await session.flush()
    log.info(
        "drive.watch.registered",
        connector_id=str(connector_id),
        folder_id=folder_id,
        channel_id=channel_id,
        expires_at=expires_at,
    )
    return record


def _decrypt_access_token(vault: TokenVault, blob: str) -> str:
    payload = json.loads(vault.decrypt(blob))
    return str(payload["access_token"])


async def _renew_one(
    *,
    session: AsyncSession,
    settings: Settings,
    vault: TokenVault,
    channel_row: models.ConnectorChannel,
    record: WatchRecord,
    now: int,
) -> bool:
    """Re-register `channel_row` if it expires within RENEW_BUFFER_SECONDS."""
    if record.expires_at > now + RENEW_BUFFER_SECONDS:
        return False
    connector = await session.get(models.Connector, channel_row.connector_id)
    if connector is None:
        return False
    access_token = _decrypt_access_token(vault, connector.credentials_secret)
    client = DriveClient(access_token=access_token)
    try:
        await register_watch(
            session=session,
            settings=settings,
            drive_client=client,
            connector_id=channel_row.connector_id,
            folder_id=record.folder_id,
            now=now,
        )
    finally:
        await client.aclose()
    return True


async def renew_drive_watches(now: int | None = None) -> dict[str, int]:
    """Find watches that expire soon and re-register them.

    Returns `{scanned, renewed}` counts. Wrap-in-Celery is in
    `jobs/celery_tasks.py` as `evercurrent.renew_drive_watches`.
    """
    settings = get_settings()
    if settings.connector_secret_key is None:
        log.warning("drive.renew.missing_secret_key")
        return {"scanned": 0, "renewed": 0}
    vault = TokenVault(settings.connector_secret_key)
    now_ts = now if now is not None else int(time.time())
    scanned = 0
    renewed = 0

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(models.ConnectorChannel).join(
                    models.Connector,
                    models.Connector.id == models.ConnectorChannel.connector_id,
                ).where(models.Connector.kind == "drive"),
            )
        ).scalars().all()
        for row in rows:
            scanned += 1
            record = decode_watch_metadata(row.name)
            if record is None:
                continue
            try:
                did_renew = await _renew_one(
                    session=session,
                    settings=settings,
                    vault=vault,
                    channel_row=row,
                    record=record,
                    now=now_ts,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "drive.renew.failed",
                    folder_id=record.folder_id,
                    error=str(exc),
                )
                continue
            if did_renew:
                renewed += 1
        await session.commit()

    log.info("drive.renew.done", scanned=scanned, renewed=renewed)
    return {"scanned": scanned, "renewed": renewed}


def soon_to_expire(record: WatchRecord, *, now: int) -> bool:
    """Pure helper kept exposed for testability of the renewal predicate."""
    return record.expires_at <= now + RENEW_BUFFER_SECONDS


def _hours_until(expires_at: int, *, now: int) -> float:
    return (expires_at - now) / 3600.0


def _format_expiry(expires_at: int) -> str:
    return dt.datetime.fromtimestamp(expires_at, tz=dt.UTC).isoformat()


__all__ = [
    "RENEW_BUFFER_SECONDS",
    "WATCH_TTL_SECONDS",
    "WatchRecord",
    "decode_watch_metadata",
    "encode_watch_metadata",
    "register_watch",
    "renew_drive_watches",
    "soon_to_expire",
]
