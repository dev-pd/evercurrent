"""Immediate DM for a critical Card.

Smaller payload than the digest path: title + one-line summary + a
single "Open card" button. The user can opt to override quiet hours
for this kind by setting `value='override_quiet'` on their
`urgent_immediate` subscription — otherwise we defer the same way the
digest path does.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.notify import quiet_hours, repository
from evercurrent.notify.slack_deliver import (
    DeliveryResult,
    SlackRateLimitedError,
)
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)

_URGENT_KIND = "urgent_immediate"
_CHANNEL_SLACK_DM = "slack_dm"
_CHANNEL_SKIPPED = "skipped"
_OVERRIDE_VALUE = "override_quiet"


def _zoneinfo_safe(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


async def _load_card_member(
    session: AsyncSession,
    *,
    card_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> tuple[models.Card, models.OrgMembership] | None:
    card = (
        await session.execute(
            select(models.Card).where(models.Card.id == card_id),
        )
    ).scalar_one_or_none()
    membership = (
        await session.execute(
            select(models.OrgMembership).where(
                models.OrgMembership.id == membership_id,
            ),
        )
    ).scalar_one_or_none()
    if card is None or membership is None:
        return None
    return card, membership


async def _load_subscription(
    session: AsyncSession,
    *,
    membership_id: uuid.UUID,
) -> models.Subscription | None:
    return (
        await session.execute(
            select(models.Subscription).where(
                models.Subscription.membership_id == membership_id,
                models.Subscription.kind == _URGENT_KIND,
            ),
        )
    ).scalars().first()


def _card_blocks(card: models.Card) -> list[dict[str, Any]]:
    web_url = get_settings().next_public_api_url.rstrip("/")
    open_url = f"{web_url}/decisions/{card.id}"
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Urgent · {card.kind}"[:150],
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{card.summary}*"[:3000]},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Open card",
                        "emoji": True,
                    },
                    "url": open_url,
                },
            ],
        },
    ]


async def _load_bot_token(
    session: AsyncSession, *, org_id: uuid.UUID,
) -> str | None:
    connector = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.org_id == org_id,
                models.Connector.kind == "slack",
            ),
        )
    ).scalar_one_or_none()
    if connector is None or not connector.credentials_secret:
        return None
    settings = get_settings()
    if settings.connector_secret_key is None:
        return None
    return TokenVault(settings.connector_secret_key).decrypt(
        connector.credentials_secret,
    )


def _classify_slack_error(exc: SlackAPIError) -> None:
    if exc.error in {"ratelimited", "rate_limited_persistent"}:
        raise SlackRateLimitedError from exc
    log.warning("notify.urgent.error", error=exc.error)


async def deliver_urgent_dm(  # noqa: PLR0911
    session: AsyncSession,
    card_id: uuid.UUID,
    membership_id: uuid.UUID,
    *,
    slack_client: SlackClient | None = None,
    now: dt.datetime | None = None,
) -> DeliveryResult:
    now = now or dt.datetime.now(dt.UTC)
    loaded = await _load_card_member(
        session, card_id=card_id, membership_id=membership_id,
    )
    if loaded is None:
        return DeliveryResult(status="missing", reason="card_or_member_missing")
    card, membership = loaded

    if membership.slack_user_id is None:
        return DeliveryResult(status="skipped", reason="no_slack_user")

    await set_org_context(session, membership.org_id)

    subscription = await _load_subscription(session, membership_id=membership.id)
    if subscription is not None and not subscription.enabled:
        notif_id = await repository.insert_notification(
            session,
            org_id=membership.org_id,
            membership_id=membership.id,
            kind=_URGENT_KIND,
            channel=_CHANNEL_SKIPPED,
            payload={"reason": "subscription_disabled", "card_id": str(card_id)},
        )
        await session.commit()
        return DeliveryResult(
            status="skipped",
            notification_id=notif_id,
            reason="subscription_disabled",
        )

    override = (
        subscription is not None
        and subscription.value == _OVERRIDE_VALUE
        and subscription.enabled
    )

    tz = _zoneinfo_safe(membership.timezone)
    if (
        not override
        and membership.quiet_start is not None
        and membership.quiet_end is not None
        and quiet_hours.is_within_quiet(
            now,
            tz=tz,
            quiet_start=membership.quiet_start,
            quiet_end=membership.quiet_end,
        )
    ):
        eta = quiet_hours.next_open(
            now, tz=tz, quiet_end=membership.quiet_end,
        )
        return DeliveryResult(status="deferred", deferred_eta=eta)

    bot_token = await _load_bot_token(session, org_id=membership.org_id)
    if bot_token is None:
        notif_id = await repository.insert_notification(
            session,
            org_id=membership.org_id,
            membership_id=membership.id,
            kind=_URGENT_KIND,
            channel=_CHANNEL_SKIPPED,
            payload={"reason": "no_bot_token", "card_id": str(card_id)},
        )
        await session.commit()
        return DeliveryResult(
            status="skipped",
            notification_id=notif_id,
            reason="no_bot_token",
        )

    blocks = _card_blocks(card)
    client = slack_client or SlackClient(bot_token)
    try:
        resp = await client.chat_post_message(
            channel=membership.slack_user_id,
            text=f"Urgent: {card.summary}",
            blocks=blocks,
        )
    except SlackAPIError as exc:
        _classify_slack_error(exc)
        return DeliveryResult(status="failed", reason=exc.error)
    finally:
        if slack_client is None:
            await client.aclose()

    payload: dict[str, Any] = {
        "card_id": str(card_id),
        "ts": resp.get("ts"),
        "channel": resp.get("channel"),
    }
    notif_id = await repository.insert_notification(
        session,
        org_id=membership.org_id,
        membership_id=membership.id,
        kind=_URGENT_KIND,
        channel=_CHANNEL_SLACK_DM,
        payload=payload,
    )
    await session.commit()
    return DeliveryResult(status="sent", notification_id=notif_id)
