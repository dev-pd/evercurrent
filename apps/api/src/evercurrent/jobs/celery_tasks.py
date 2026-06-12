"""Celery task wrappers around the async business logic.

Each task is a thin sync function that calls `asyncio.run(...)` on the
existing async implementation. Keep tasks small + side-effect-only;
all real work lives in the domain modules.
"""

from __future__ import annotations

import asyncio
import uuid as _uuid
from typing import Any

import structlog

from evercurrent.jobs.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run(coro: Any) -> Any:
    """Run an async coroutine in a fresh event loop.

    Celery tasks are sync; each task gets its own loop because SQLAlchemy
    async + asyncpg bind their connection pool to whatever loop was alive
    when the engine was built. After the coroutine finishes we dispose the
    engine so the next task rebuilds the pool on its own loop — otherwise
    asyncpg raises "Future attached to a different loop".
    """
    from evercurrent.db.session import dispose_engine

    async def _wrapper() -> Any:
        try:
            return await coro
        finally:
            await dispose_engine()

    return asyncio.run(_wrapper())


@celery_app.task(name="evercurrent.heartbeat")
def heartbeat() -> str:
    import datetime as dt

    return dt.datetime.now(dt.UTC).isoformat()


@celery_app.task(name="evercurrent.ingest_document")
def ingest_document(document_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.ingest_doc import ingest_document as impl

    return _run(impl({}, document_id))


@celery_app.task(name="evercurrent.route_message")
def route_message(raw_event_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.route_message import route_message as impl

    return _run(impl({}, raw_event_id))


@celery_app.task(name="evercurrent.build_card")
def build_card(message_id: str, kind: str, summary_hint: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.build_card import build_card as impl

    return _run(impl({}, message_id, kind, summary_hint))


@celery_app.task(name="evercurrent.score_message_for_members")
def score_message_for_members(message_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.score_message import score_message_for_members as impl

    return _run(impl({}, message_id))


@celery_app.task(name="evercurrent.generate_digest_for_member")
def generate_digest_for_member(
    project_member_id: str,
    day_index: int,
    phase: str,
    force: bool = False,
) -> dict[str, Any]:
    from evercurrent.jobs.tasks.generate_digest_for_member import (
        generate_digest_for_member as impl,
    )

    return _run(impl({}, project_member_id, day_index, phase, force))


@celery_app.task(name="evercurrent.enqueue_due_digests_now")
def enqueue_due_digests_now() -> list[dict[str, Any]]:
    from evercurrent.digest.scheduler import enqueue_due_digests_now as impl

    return _run(impl())


def _new_task_id() -> str:
    return str(_uuid.uuid4())


@celery_app.task(
    name="evercurrent.deliver_digest_dm",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def deliver_digest_dm(
    self: Any,
    digest_id: str,
    force_quiet: bool = False,
) -> dict[str, Any]:
    from evercurrent.jobs.tasks.deliver_digest import deliver_digest_dm_task as impl
    from evercurrent.notify.slack_deliver import SlackRateLimitedError

    try:
        return _run(impl({}, digest_id, force_quiet))
    except SlackRateLimitedError as exc:
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="evercurrent.deliver_urgent_dm",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def deliver_urgent_dm(
    self: Any,
    card_id: str,
    membership_id: str,
) -> dict[str, Any]:
    from evercurrent.jobs.tasks.deliver_urgent import deliver_urgent_dm_task as impl
    from evercurrent.notify.slack_deliver import SlackRateLimitedError

    try:
        return _run(impl({}, card_id, membership_id))
    except SlackRateLimitedError as exc:
        raise self.retry(exc=exc) from exc
