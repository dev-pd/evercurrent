from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.notify import block_kit, quiet_hours, repository
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)

_DIGEST_KIND = "morning_digest"
_URGENT_KIND = "urgent_immediate"
_CHANNEL_SLACK_DM = "slack_dm"
_CHANNEL_SKIPPED = "skipped"


class SlackRateLimitedError(RuntimeError):
    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("slack rate limited")
        self.retry_after = retry_after


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    notification_id: uuid.UUID | None = None
    deferred_eta: dt.datetime | None = None
    reason: str | None = None


async def _load_digest_member(
    session: AsyncSession,
    digest_id: uuid.UUID,
) -> tuple[models.Digest, models.OrgMembership] | None:
    digest_row = (
        await session.execute(
            select(models.Digest).where(models.Digest.id == digest_id),
        )
    ).scalar_one_or_none()
    if digest_row is None:
        return None
    membership_row = (
        await session.execute(
            select(models.OrgMembership).where(
                models.OrgMembership.id == digest_row.project_member_id,
            ),
        )
    ).scalar_one_or_none()
    if membership_row is None:
        return None
    return digest_row, membership_row


async def _load_subscription(
    session: AsyncSession,
    *,
    membership_id: uuid.UUID,
    kind: str,
) -> models.Subscription | None:
    return (
        (
            await session.execute(
                select(models.Subscription).where(
                    models.Subscription.membership_id == membership_id,
                    models.Subscription.kind == kind,
                ),
            )
        )
        .scalars()
        .first()
    )


def _zoneinfo_safe(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


async def _load_bot_token(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
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
    vault = TokenVault(settings.connector_secret_key)
    return vault.decrypt(connector.credentials_secret)


def _classify_slack_error(exc: SlackAPIError) -> None:
    if exc.error in {"ratelimited", "rate_limited_persistent"}:
        raise SlackRateLimitedError from exc
    log.warning("notify.slack.error", error=exc.error)


async def deliver_digest_dm(  # noqa: PLR0911
    session: AsyncSession,
    digest_id: uuid.UUID,
    *,
    force_quiet: bool = False,
    slack_client: SlackClient | None = None,
    now: dt.datetime | None = None,
) -> DeliveryResult:
    now = now or dt.datetime.now(dt.UTC)
    loaded = await _load_digest_member(session, digest_id)
    if loaded is None:
        return DeliveryResult(status="missing", reason="digest_or_member_missing")
    digest_row, membership = loaded

    if membership.slack_user_id is None:
        log.info("notify.digest.skip_no_slack", digest_id=str(digest_id))
        return DeliveryResult(status="skipped", reason="no_slack_user")

    await set_org_context(session, membership.org_id)

    subscription = await _load_subscription(
        session,
        membership_id=membership.id,
        kind=_DIGEST_KIND,
    )
    if subscription is not None and not subscription.enabled:
        notif_id = await repository.insert_notification(
            session,
            org_id=membership.org_id,
            membership_id=membership.id,
            kind=_DIGEST_KIND,
            channel=_CHANNEL_SKIPPED,
            payload={"reason": "subscription_disabled", "digest_id": str(digest_id)},
        )
        await session.commit()
        return DeliveryResult(
            status="skipped",
            notification_id=notif_id,
            reason="subscription_disabled",
        )

    tz = _zoneinfo_safe(membership.timezone)
    quiet_start = membership.quiet_start
    quiet_end = membership.quiet_end
    if (
        not force_quiet
        and quiet_start is not None
        and quiet_end is not None
        and quiet_hours.is_within_quiet(
            now,
            tz=tz,
            quiet_start=quiet_start,
            quiet_end=quiet_end,
        )
    ):
        eta = quiet_hours.next_open(now, tz=tz, quiet_end=quiet_end)
        log.info(
            "notify.digest.deferred",
            digest_id=str(digest_id),
            eta=eta.isoformat(),
        )
        return DeliveryResult(status="deferred", deferred_eta=eta)

    title = f"Day {digest_row.day_index} · {digest_row.phase}"
    blocks = block_kit.digest_to_blocks(digest_row.content_md, title=title)

    bot_token = await _load_bot_token(session, org_id=membership.org_id)
    if bot_token is None:
        notif_id = await repository.insert_notification(
            session,
            org_id=membership.org_id,
            membership_id=membership.id,
            kind=_DIGEST_KIND,
            channel=_CHANNEL_SKIPPED,
            payload={"reason": "no_bot_token", "digest_id": str(digest_id)},
        )
        await session.commit()
        return DeliveryResult(
            status="skipped",
            notification_id=notif_id,
            reason="no_bot_token",
        )

    client = slack_client or SlackClient(bot_token)
    try:
        resp = await client.chat_post_message(
            channel=membership.slack_user_id,
            text=title,
            blocks=blocks,
        )
    except SlackAPIError as exc:
        _classify_slack_error(exc)
        return DeliveryResult(status="failed", reason=exc.error)
    finally:
        if slack_client is None:
            await client.aclose()

    payload: dict[str, Any] = {
        "digest_id": str(digest_id),
        "ts": resp.get("ts"),
        "channel": resp.get("channel"),
    }
    notif_id = await repository.insert_notification(
        session,
        org_id=membership.org_id,
        membership_id=membership.id,
        kind=_DIGEST_KIND,
        channel=_CHANNEL_SLACK_DM,
        payload=payload,
    )
    await session.commit()
    return DeliveryResult(status="sent", notification_id=notif_id)
