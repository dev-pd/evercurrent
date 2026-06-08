"""Drive push-notification webhook handler.

Drive push is a kick, not a payload: the headers tell us "something
changed in this channel", and we have to diff against `files.list` to
discover *what* changed. The handler verifies both `X-Goog-Channel-Id`
(maps to a row we own) and `X-Goog-Channel-Token` (matches the random
token we stored at watch-registration time), then enqueues an
`ingest_document` task per changed file.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings
from evercurrent.connectors.drive.client import DriveClient
from evercurrent.connectors.drive.watch import decode_watch_metadata
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)

RESOURCE_STATE_SYNC = "sync"
RESOURCE_STATE_ADD = "add"
RESOURCE_STATE_CHANGE = "change"
RESOURCE_STATE_UPDATE = "update"

EnqueueIngestDocument = Callable[..., None]
DriveClientFactory = Callable[..., DriveClient]


def _default_drive_client_factory(access_token: str) -> DriveClient:
    return DriveClient(access_token=access_token)


@dataclass(frozen=True)
class DriveWebhookResult:
    """What the handler decided to do, surfaced for the route + tests."""

    status_code: int
    body: dict[str, Any]
    enqueued_file_ids: list[str]


async def _channel_lookup(
    *,
    session: AsyncSession,
    channel_id: str,
) -> models.ConnectorChannel | None:
    rows = (
        await session.execute(select(models.ConnectorChannel))
    ).scalars().all()
    for row in rows:
        record = decode_watch_metadata(row.name)
        if record is not None and record.channel_id == channel_id:
            return row
    return None


def _is_pdf(mime_type: str) -> bool:
    return mime_type == "application/pdf"


def _is_google_doc(mime_type: str) -> bool:
    return mime_type == "application/vnd.google-apps.document"


async def handle_drive_webhook(  # noqa: C901, PLR0911
    *,
    session: AsyncSession,
    settings: Settings,
    channel_id: str | None,
    channel_token: str | None,
    resource_state: str | None,
    resource_id: str | None,  # noqa: ARG001
    enqueue_ingest_document: EnqueueIngestDocument | None = None,
    drive_client_factory: DriveClientFactory | None = None,
    now: float | None = None,
) -> DriveWebhookResult:
    """Run the full Drive webhook pipeline. Returns the result the route returns."""
    if channel_id is None or channel_token is None:
        return DriveWebhookResult(
            status_code=401,
            body={"ok": False, "error": "missing channel headers"},
            enqueued_file_ids=[],
        )

    channel_row = await _channel_lookup(session=session, channel_id=channel_id)
    if channel_row is None:
        log.info("drive.webhook.unknown_channel", channel_id=channel_id)
        return DriveWebhookResult(
            status_code=401,
            body={"ok": False, "error": "unknown channel"},
            enqueued_file_ids=[],
        )

    record = decode_watch_metadata(channel_row.name)
    if record is None or not _constant_time_eq(record.channel_token, channel_token):
        log.warning("drive.webhook.bad_token", channel_id=channel_id)
        return DriveWebhookResult(
            status_code=401,
            body={"ok": False, "error": "bad channel token"},
            enqueued_file_ids=[],
        )

    if resource_state == RESOURCE_STATE_SYNC:
        # Initial handshake — Drive sends one of these per channel at
        # registration time. Treat as no-op.
        return DriveWebhookResult(
            status_code=200,
            body={"ok": True, "skipped": "sync"},
            enqueued_file_ids=[],
        )

    if resource_state not in (
        RESOURCE_STATE_ADD,
        RESOURCE_STATE_CHANGE,
        RESOURCE_STATE_UPDATE,
    ):
        return DriveWebhookResult(
            status_code=200,
            body={"ok": True, "skipped": str(resource_state)},
            enqueued_file_ids=[],
        )

    connector = await session.get(models.Connector, channel_row.connector_id)
    if connector is None:
        return DriveWebhookResult(
            status_code=200,
            body={"ok": True, "skipped": "connector missing"},
            enqueued_file_ids=[],
        )
    await set_org_context(session, connector.org_id)

    if settings.connector_secret_key is None:
        log.error("drive.webhook.no_secret_key")
        return DriveWebhookResult(
            status_code=503,
            body={"ok": False},
            enqueued_file_ids=[],
        )
    vault = TokenVault(settings.connector_secret_key)
    blob = vault.decrypt(connector.credentials_secret)
    token_payload = json.loads(blob)
    access_token = str(token_payload["access_token"])

    factory = drive_client_factory or _default_drive_client_factory
    client = factory(access_token)
    enqueued: list[str] = []
    try:
        page = await client.files_list(
            query=f"'{record.folder_id}' in parents and trashed = false",
            page_size=100,
        )
        for f in page.files:
            if not (_is_pdf(f.mime_type) or _is_google_doc(f.mime_type)):
                continue
            if enqueue_ingest_document is not None:
                try:
                    enqueue_ingest_document(
                        connector_id=connector.id,
                        drive_file_id=f.id,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "drive.webhook.enqueue_failed",
                        file_id=f.id,
                        error=str(exc),
                    )
                    continue
            enqueued.append(f.id)
    finally:
        await client.aclose()

    _ = now
    log.info(
        "drive.webhook.handled",
        channel_id=channel_id,
        resource_state=resource_state,
        enqueued=len(enqueued),
    )
    return DriveWebhookResult(
        status_code=200,
        body={"ok": True, "enqueued": len(enqueued)},
        enqueued_file_ids=enqueued,
    )


def _constant_time_eq(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    diff = 0
    for x, y in zip(a.encode(), b.encode(), strict=False):
        diff |= x ^ y
    return diff == 0


# Helpers exported so the route can keep a thin signature.

async def discover_folders(
    *,
    session: AsyncSession,
    settings: Settings,
    vault: TokenVault,
    connector_id: uuid.UUID,
    client_factory: DriveClientFactory | None = None,
) -> list[dict[str, str]]:
    """List Drive folders the connector can see, for the picker UI."""
    connector = await session.get(models.Connector, connector_id)
    if connector is None:
        return []
    _ = settings
    blob = vault.decrypt(connector.credentials_secret)
    token_payload = json.loads(blob)
    access_token = str(token_payload["access_token"])

    factory = client_factory or _default_drive_client_factory
    client = factory(access_token)
    try:
        page = await client.files_list(
            query="mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            page_size=100,
        )
    finally:
        await client.aclose()
    return [{"id": f.id, "name": f.name} for f in page.files]


WaitFn = Callable[[float], Awaitable[None]]


def _now_seconds() -> float:
    return time.time()
