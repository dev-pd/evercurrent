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


@celery_app.task(name="evercurrent.refresh_today")
def refresh_today(project_name: str | None = None) -> dict[str, Any]:
    from evercurrent.jobs.tasks.refresh_today import refresh_today as impl

    result = _run(impl({}, project_name))
    project_id = result.get("project_id") if isinstance(result, dict) else None
    if project_id:
        publish_event(
            project_id,
            "digest.updated",
            {"day": result.get("day"), "phase": result.get("phase")},
        )
    return result


@celery_app.task(name="evercurrent.synthesize_today_message")
def synthesize_today_message(project_name: str | None = None) -> dict[str, Any]:
    from evercurrent.jobs.tasks.refresh_today import synthesize_today_message as impl

    result = _run(impl({}, project_name))
    msgs = result.get("messages") if isinstance(result, dict) else None
    if isinstance(msgs, list) and msgs:
        # Inserted messages carry no project_id at this layer; publish
        # under the project_name's resolved id is overkill — just emit a
        # generic 'message.synthesized' on a project-scoped lookup.
        from evercurrent.db.repositories import ProjectRepository
        from evercurrent.db.session import session_scope

        async def _publish_for(name: str | None) -> None:
            async with session_scope() as session:
                proj = await ProjectRepository(session).get_by_name(
                    name or "Warehouse Robot v2",
                )
            if proj is not None:
                publish_event(proj.id, "message.synthesized", {"count": len(msgs)})

        _run(_publish_for(project_name))
    return result


@celery_app.task(name="evercurrent.enrich_day")
def enrich_day(project_id: str, day: int) -> dict[str, Any]:
    from evercurrent.jobs.tasks.enrich_messages import enrich_day as impl

    return _run(impl({}, project_id, day))


@celery_app.task(name="evercurrent.advance_day")
def advance_day(project_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.advance_day import advance_day as impl

    return _run(impl({}, project_id))


@celery_app.task(name="evercurrent.extract_decisions_for_day")
def extract_decisions_for_day(project_id: str, day: int) -> dict[str, Any]:
    from evercurrent.jobs.tasks.extract_decisions import extract_decisions_for_day as impl

    return _run(impl({}, project_id, day))


@celery_app.task(name="evercurrent.generate_all_digests")
def generate_all_digests(project_id: str, day: int) -> dict[str, Any]:
    from evercurrent.jobs.tasks.generate_digests import generate_all_digests as impl

    return _run(impl({}, project_id, day))


@celery_app.task(name="evercurrent.ingest_document")
def ingest_document(document_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.ingest_doc import ingest_document as impl

    return _run(impl({}, document_id))


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
