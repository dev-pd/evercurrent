"""Deliver a per-user digest as a Slack DM (Phase 11).

This async impl is invoked by the sync Celery wrapper in
`jobs.celery_tasks`. We open our own session here (no FastAPI request
scope) and delegate to the notify package.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.session import session_scope
from evercurrent.notify.slack_deliver import deliver_digest_dm

log = structlog.get_logger(__name__)


async def deliver_digest_dm_task(
    _ctx: dict[str, Any],
    digest_id: str,
    force_quiet: bool = False,
) -> dict[str, Any]:
    parsed = uuid.UUID(digest_id)
    async with session_scope() as session:
        result = await deliver_digest_dm(
            session,
            parsed,
            force_quiet=force_quiet,
        )
    log.info(
        "notify.digest.delivered",
        digest_id=digest_id,
        status=result.status,
        reason=result.reason,
    )
    payload: dict[str, Any] = {
        "digest_id": digest_id,
        "status": result.status,
        "reason": result.reason,
    }
    if result.deferred_eta is not None:
        payload["deferred_eta"] = result.deferred_eta.isoformat()
    if result.notification_id is not None:
        payload["notification_id"] = str(result.notification_id)
    return payload
