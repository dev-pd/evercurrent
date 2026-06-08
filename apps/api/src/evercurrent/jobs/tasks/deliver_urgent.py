"""Deliver an urgent Card alert as a Slack DM (Phase 11)."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.session import session_scope
from evercurrent.notify.urgent_deliver import deliver_urgent_dm

log = structlog.get_logger(__name__)


async def deliver_urgent_dm_task(
    _ctx: dict[str, Any],
    card_id: str,
    membership_id: str,
) -> dict[str, Any]:
    card_uuid = uuid.UUID(card_id)
    member_uuid = uuid.UUID(membership_id)
    async with session_scope() as session:
        result = await deliver_urgent_dm(session, card_uuid, member_uuid)
    log.info(
        "notify.urgent.delivered",
        card_id=card_id,
        membership_id=membership_id,
        status=result.status,
        reason=result.reason,
    )
    payload: dict[str, Any] = {
        "card_id": card_id,
        "membership_id": membership_id,
        "status": result.status,
        "reason": result.reason,
    }
    if result.deferred_eta is not None:
        payload["deferred_eta"] = result.deferred_eta.isoformat()
    if result.notification_id is not None:
        payload["notification_id"] = str(result.notification_id)
    return payload
