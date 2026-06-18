"""Background Slack sync: channel discovery + backfill + author provisioning.

Runs as a Celery task so a large backfill (many channels, thread hydration,
Slack rate limits) never depends on the HTTP request staying alive.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select, text

from evercurrent.api.routes.connectors import _provision_authors
from evercurrent.config import get_settings
from evercurrent.connectors.slack.backfill import backfill_channel
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.db.session import admin_session_scope

log = structlog.get_logger(__name__)


async def sync_slack_connector(_ctx: dict[str, Any], connector_id: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.connector_secret_key is None:
        msg = "CONNECTOR_SECRET_KEY is not configured"
        raise RuntimeError(msg)
    vault = TokenVault(settings.connector_secret_key)
    cid = uuid.UUID(connector_id)
    async with admin_session_scope() as session:
        connector = (
            await session.execute(
                select(models.Connector).where(
                    models.Connector.id == cid,
                    models.Connector.kind == "slack",
                ),
            )
        ).scalar_one_or_none()
        if connector is None:
            return {"status": "missing", "connector_id": connector_id}

        token = vault.decrypt(connector.credentials_secret)
        client = SlackClient(bot_token=token)
        raw_total = 0
        channels_done = 0
        members = 0
        try:
            channels = await client.list_all_channels()
            for ch in channels:
                if ch.is_archived:
                    continue
                cc_id = (
                    await session.execute(
                        text(
                            "INSERT INTO connector_channels "
                            "(org_id, connector_id, external_id, name, ingest) "
                            "VALUES (:o, :c, :e, :n, true) "
                            "ON CONFLICT (connector_id, external_id) "
                            "DO UPDATE SET name = EXCLUDED.name RETURNING id",
                        ),
                        {
                            "o": str(connector.org_id),
                            "c": str(connector.id),
                            "e": ch.id,
                            "n": ch.name,
                        },
                    )
                ).scalar_one()
                await session.commit()
                try:
                    summary = await backfill_channel(
                        session=session,
                        vault=vault,
                        connector_channel_id=cc_id,
                        slack_client=client,
                    )
                    raw_total += summary.raw_events_inserted
                    channels_done += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("slack.sync.channel_failed", channel=ch.name, error=str(exc))
            members = await _provision_authors(session, client, connector.org_id)
        finally:
            await client.aclose()

    # Draft each member's first digest now that messages are ingested. Delayed so
    # the per-message scoring/signal tasks enqueued during backfill drain before
    # the digest reads from them.
    from evercurrent.jobs.celery_app import celery_app

    celery_app.send_task("evercurrent.enqueue_due_digests_now", countdown=20)

    log.info(
        "slack.sync.done",
        connector_id=connector_id,
        channels=channels_done,
        raw_events=raw_total,
        members=members,
    )
    return {
        "status": "ok",
        "channels": channels_done,
        "raw_events": raw_total,
        "members": members,
    }
