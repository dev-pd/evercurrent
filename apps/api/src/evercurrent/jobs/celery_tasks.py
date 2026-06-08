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
from evercurrent.realtime import publish_event

log = structlog.get_logger(__name__)


def _run(coro: Any) -> Any:
    """Run an async coroutine in a fresh event loop.

    Celery tasks are sync; we don't share the loop across tasks because
    SQLAlchemy async + asyncpg dislike loop reuse from a worker pool.
    """
    return asyncio.run(coro)


@celery_app.task(name="evercurrent.heartbeat")
def heartbeat() -> str:
    import datetime as dt

    return dt.datetime.now(dt.UTC).isoformat()


@celery_app.task(name="evercurrent.generate_all_digests")
def generate_all_digests(project_id: str, day: int) -> dict[str, Any]:
    from evercurrent.jobs.tasks.generate_digests import generate_all_digests as impl

    return _run(impl({}, project_id, day))


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


@celery_app.task(name="evercurrent.regenerate_user_digest")
def regenerate_user_digest(
    project_id: str,
    user_id: str,
    day: int,
    phase: str | None = None,
) -> dict[str, Any]:
    from evercurrent.jobs.tasks.regenerate_user_digest import regenerate_user_digest as impl

    result = _run(impl({}, project_id, user_id, day, phase))
    publish_event(
        project_id,
        "digest.updated",
        {"user_id": user_id, "day": day, "phase": phase},
    )
    return result


def _new_task_id() -> str:
    return str(_uuid.uuid4())
