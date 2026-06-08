"""Notification + subscription persistence.

Repositories return domain-shaped payloads (Pydantic schemas where it
makes sense, plain dicts where the caller will turn around and send to
JSON anyway). Sessions are passed in — never created here.
"""

from __future__ import annotations

import uuid
from typing import Any, cast, get_args

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db import models
from evercurrent.notify.schemas import SubscriptionItem, SubscriptionKind

_VALID_KINDS: frozenset[str] = frozenset(get_args(SubscriptionKind))


async def list_subscriptions(
    session: AsyncSession,
    *,
    membership_id: uuid.UUID,
) -> list[SubscriptionItem]:
    rows = (
        await session.execute(
            select(models.Subscription).where(
                models.Subscription.membership_id == membership_id,
            ),
        )
    ).scalars().all()
    out: list[SubscriptionItem] = []
    for row in rows:
        if row.kind not in _VALID_KINDS:
            continue
        out.append(
            SubscriptionItem(
                kind=cast("SubscriptionKind", row.kind),
                value=row.value,
                enabled=row.enabled,
            ),
        )
    return out


async def replace_subscriptions(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    membership_id: uuid.UUID,
    items: list[SubscriptionItem],
) -> list[SubscriptionItem]:
    """Replace the full subscription set for a member atomically.

    Caller is responsible for the transaction boundary (commit/rollback);
    we just emit the delete + inserts on the provided session so the
    whole replace is one unit of work.
    """
    await session.execute(
        delete(models.Subscription).where(
            models.Subscription.membership_id == membership_id,
        ),
    )
    for item in items:
        session.add(
            models.Subscription(
                org_id=org_id,
                membership_id=membership_id,
                kind=item.kind,
                value=item.value,
                enabled=item.enabled,
            ),
        )
    await session.flush()
    return await list_subscriptions(session, membership_id=membership_id)


async def insert_notification(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    membership_id: uuid.UUID,
    kind: str,
    channel: str,
    payload: dict[str, Any],
) -> uuid.UUID:
    row = models.Notification(
        org_id=org_id,
        membership_id=membership_id,
        kind=kind,
        channel=channel,
        payload=payload,
    )
    session.add(row)
    await session.flush()
    return row.id
