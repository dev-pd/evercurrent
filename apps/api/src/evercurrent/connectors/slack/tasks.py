"""Celery task entrypoints owned by the Slack connector.

Phase 3 only needs a stub: `route_message(raw_event_id)` is enqueued by
the events webhook so we can verify the wiring. Phase 5 replaces the
body with the real router-agent + normalisation logic. We expose
`route_message_task` (the Celery binding) for direct import, and
`SLACK_SEED_TASKS` so `jobs/celery_tasks.py` can pull the registry
without knowing about individual task names.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import text

from evercurrent.db.session import session_scope
from evercurrent.jobs.celery_app import celery_app

log = structlog.get_logger(__name__)


async def _route_message(raw_event_id: str) -> dict[str, Any]:
    """Phase 3 stub: load the raw event, log, return.

    Phase 5 replaces this with the router-agent call + normalisation
    into `messages` + `message_tags`.
    """
    parsed = uuid.UUID(raw_event_id)
    async with session_scope() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, source, external_id, org_id "
                    "FROM raw_events WHERE id = :id",
                ),
                {"id": str(parsed)},
            )
        ).first()
    if row is None:
        log.warning("slack.route_message.missing", raw_event_id=raw_event_id)
        return {"raw_event_id": raw_event_id, "status": "missing"}
    log.info(
        "slack.route_message.received",
        raw_event_id=raw_event_id,
        source=row.source,
        external_id=row.external_id,
    )
    return {"raw_event_id": raw_event_id, "status": "stub_ack"}


@celery_app.task(name="evercurrent.route_message")
def route_message_task(raw_event_id: str) -> dict[str, Any]:
    """Celery binding around `_route_message`. Always sync wrapper around async."""
    return asyncio.run(_route_message(raw_event_id))


def enqueue_route_message(*, raw_event_id: uuid.UUID) -> None:
    """Helper used by the webhook to enqueue without importing Celery types."""
    route_message_task.delay(str(raw_event_id))


SLACK_SEED_TASKS: tuple[str, ...] = ("evercurrent.route_message",)
