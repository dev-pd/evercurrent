"""Celery task registry: thin sync wrappers that run the async task impls from
jobs/tasks/. Task name strings are the public contract — keep them stable."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from evercurrent.jobs.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run(coro: Any) -> Any:
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


@celery_app.task(name="evercurrent.emit_demo_chatter")
def emit_demo_chatter() -> dict[str, Any]:
    from evercurrent.jobs.tasks.demo_chatter import emit_chatter as impl

    return _run(impl({}))


@celery_app.task(name="evercurrent.sync_slack_connector")
def sync_slack_connector(connector_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.sync_slack import sync_slack_connector as impl

    return _run(impl({}, connector_id))


@celery_app.task(name="evercurrent.generate_eve_insight")
def generate_eve_insight(project_id: str, org_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.eve_insight import generate_eve_insight as impl

    return _run(impl({}, project_id, org_id))


@celery_app.task(name="evercurrent.sync_dropbox_connector")
def sync_dropbox_connector(connector_id: str) -> dict[str, Any]:
    from evercurrent.jobs.tasks.sync_dropbox import sync_dropbox_connector as impl

    return _run(impl({}, connector_id))
