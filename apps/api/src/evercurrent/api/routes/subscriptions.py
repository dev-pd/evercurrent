"""Subscriptions API (Phase 11).

GET returns the caller's current subscription set. PUT replaces the
full set in a single transaction so partial state on crash is
impossible.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.notify import repository
from evercurrent.notify.schemas import SubscriptionItem, SubscriptionsPayload

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


@router.get("")
async def list_subscriptions(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SubscriptionsPayload:
    items = await repository.list_subscriptions(
        session,
        membership_id=current_user.membership_id,
    )
    return SubscriptionsPayload(items=items)


@router.put("")
async def replace_subscriptions(
    payload: SubscriptionsPayload,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SubscriptionsPayload:
    items: list[SubscriptionItem]
    try:
        items = await repository.replace_subscriptions(
            session,
            org_id=current_user.org_id,
            membership_id=current_user.membership_id,
            items=payload.items,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    log.info(
        "subscriptions.replaced",
        membership_id=str(current_user.membership_id),
        count=len(items),
    )
    return SubscriptionsPayload(items=items)
