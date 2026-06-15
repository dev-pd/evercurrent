"""Run the Slack sync (channel discovery + backfill + author provisioning).

Mirrors the POST /connectors/{id}/slack/sync route but runs admin-scoped, so
it can be driven headless. Backfill enqueues route_message per raw event; the
worker then tags/scores/embeds/builds cards.

Run:  docker compose exec api python /tmp/run_sync.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, text

from evercurrent.api.routes.connectors import _provision_authors
from evercurrent.config import get_settings
from evercurrent.connectors.slack.backfill import backfill_channel
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.db.session import admin_session_scope


async def main() -> None:
    settings = get_settings()
    vault = TokenVault(settings.connector_secret_key)
    async with admin_session_scope() as session:
        connector = (
            await session.execute(
                select(models.Connector).where(models.Connector.kind == "slack"),
            )
        ).scalar_one_or_none()
        if connector is None:
            raise SystemExit("no slack connector")
        token = vault.decrypt(connector.credentials_secret)
        client = SlackClient(bot_token=token)
        raw_total = 0
        channels_done = 0
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
                        {"o": str(connector.org_id), "c": str(connector.id),
                         "e": ch.id, "n": ch.name},
                    )
                ).scalar_one()
                await session.commit()
                try:
                    summary = await backfill_channel(
                        session=session, vault=vault, connector_channel_id=cc_id,
                        days=30, slack_client=client,
                    )
                    raw_total += summary.raw_events_inserted
                    channels_done += 1
                    print(f"  #{ch.name}: +{summary.raw_events_inserted} raw")
                except Exception as exc:  # noqa: BLE001
                    print(f"  #{ch.name} backfill failed: {exc}")
            members = await _provision_authors(session, client, connector.org_id)
        finally:
            await client.aclose()
    print(f"done. channels={channels_done} raw_events={raw_total} members={members}")


if __name__ == "__main__":
    asyncio.run(main())
