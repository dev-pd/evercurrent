from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BackfillSummary:
    raw_events_inserted: int
    messages_inserted: int


async def backfill_channel(
    *,
    session: AsyncSession,
    vault: TokenVault,
    connector_channel_id: uuid.UUID,
    days: int | None = None,
    slack_client: SlackClient | None = None,
) -> BackfillSummary:
    if days is None:
        days = get_settings().slack_backfill_days
    channel_row = (
        await session.execute(
            select(models.ConnectorChannel).where(
                models.ConnectorChannel.id == connector_channel_id,
            ),
        )
    ).scalar_one_or_none()
    if channel_row is None:
        raise ValueError(f"connector_channel {connector_channel_id} not found")

    connector_row = (
        await session.execute(
            select(models.Connector).where(models.Connector.id == channel_row.connector_id),
        )
    ).scalar_one_or_none()
    if connector_row is None:
        raise ValueError("connector parent row missing")

    await set_org_context(session, connector_row.org_id)

    bot_token = vault.decrypt(connector_row.credentials_secret)
    owns_client = slack_client is None
    client = slack_client or SlackClient(bot_token=bot_token)

    raw_inserted = 0
    msg_inserted = 0
    # Slack's `oldest` rejects 7-decimal float strings; use an integer ts.
    oldest_ts = f"{int(time.time()) - days * 86400}"

    try:
        cursor: str | None = None
        while True:
            page = await client.conversations_history(
                channel=channel_row.external_id,
                oldest=oldest_ts,
                cursor=cursor,
            )
            for raw_msg in page.get("messages", []):
                inserted_raw, inserted_msg = await _persist_one(
                    session=session,
                    org_id=connector_row.org_id,
                    channel_external_id=channel_row.external_id,
                    raw=raw_msg,
                )
                raw_inserted += int(inserted_raw)
                msg_inserted += int(inserted_msg)

                if int(raw_msg.get("reply_count", 0) or 0) > 0:
                    await _hydrate_thread_replies(
                        session=session,
                        client=client,
                        org_id=connector_row.org_id,
                        channel_external_id=channel_row.external_id,
                        thread_ts=str(raw_msg["ts"]),
                    )

            cursor = page.get("response_metadata", {}).get("next_cursor") or None
            has_more = bool(page.get("has_more", False))
            if not cursor or not has_more:
                break
    finally:
        if owns_client:
            await client.aclose()

    log.info(
        "slack.backfill.done",
        channel_id=str(connector_channel_id),
        raw_inserted=raw_inserted,
        msg_inserted=msg_inserted,
    )
    return BackfillSummary(
        raw_events_inserted=raw_inserted,
        messages_inserted=msg_inserted,
    )


async def _hydrate_thread_replies(
    *,
    session: AsyncSession,
    client: SlackClient,
    org_id: uuid.UUID,
    channel_external_id: str,
    thread_ts: str,
) -> None:
    cursor: str | None = None
    while True:
        page = await client.conversations_replies(
            channel=channel_external_id,
            ts=thread_ts,
            cursor=cursor,
        )
        for raw_msg in page.get("messages", []):
            if str(raw_msg.get("ts")) == thread_ts:
                continue
            await _persist_one(
                session=session,
                org_id=org_id,
                channel_external_id=channel_external_id,
                raw=raw_msg,
            )
        cursor = page.get("response_metadata", {}).get("next_cursor") or None
        has_more = bool(page.get("has_more", False))
        if not cursor or not has_more:
            break


async def _persist_one(
    *,
    session: AsyncSession,
    org_id: uuid.UUID,
    channel_external_id: str,
    raw: dict[str, object],
) -> tuple[bool, bool]:
    external_id = str(raw.get("ts", ""))
    if not external_id:
        return (False, False)

    # Allow bot_message (one bot posting as persona usernames); skip other
    # subtypes (channel joins, edits, etc.).
    subtype = raw.get("subtype")
    if subtype is not None and subtype != "bot_message":
        return (False, False)

    payload_json = _json_dumps(raw)
    inserted_raw = False
    try:
        result = await session.execute(
            text(
                "INSERT INTO raw_events (org_id, source, external_id, payload) "
                "VALUES (:org_id, 'slack', :external_id, CAST(:payload AS jsonb)) "
                "ON CONFLICT (source, external_id) DO NOTHING "
                "RETURNING id",
            ),
            {
                "org_id": str(org_id),
                "external_id": external_id,
                "payload": payload_json,
            },
        )
        raw_event_id = result.scalar_one_or_none()
        inserted_raw = raw_event_id is not None
        if raw_event_id is not None:
            from evercurrent.jobs.celery_app import celery_app  # noqa: PLC0415

            celery_app.send_task(
                "evercurrent.route_message",
                kwargs={"raw_event_id": str(raw_event_id)},
            )
    except IntegrityError:
        await session.rollback()

    text_body = str(raw.get("text", "") or "")
    posted_at_epoch = float(external_id) if external_id else 0.0
    thread_ts = str(raw.get("thread_ts") or "")
    author = str(raw.get("username") or raw.get("user") or raw.get("bot_id") or "unknown")

    inserted_msg = False
    try:
        result = await session.execute(
            text(
                "INSERT INTO messages "
                "(org_id, source, external_id, channel, text, "
                " author_display_name, posted_at) "
                "VALUES (:org_id, 'slack', :external_id, :channel, :text, "
                "        :author, to_timestamp(:posted_at)) "
                "ON CONFLICT (source, external_id) DO NOTHING "
                "RETURNING id",
            ),
            {
                "org_id": str(org_id),
                "external_id": external_id,
                "channel": channel_external_id,
                "text": text_body,
                "author": author,
                "posted_at": posted_at_epoch,
            },
        )
        message_id = result.scalar_one_or_none()
        inserted_msg = message_id is not None
    except IntegrityError:
        await session.rollback()

    if thread_ts and thread_ts != external_id:
        await session.execute(
            text(
                "UPDATE messages SET thread_root_id = parent.id "
                "FROM messages parent "
                "WHERE messages.source = 'slack' AND messages.external_id = :ext "
                "AND parent.source = 'slack' AND parent.external_id = :parent_ext",
            ),
            {"ext": external_id, "parent_ext": thread_ts},
        )

    await session.commit()
    return (inserted_raw, inserted_msg)


def _json_dumps(obj: object) -> str:
    return json.dumps(obj, default=str, sort_keys=True)
