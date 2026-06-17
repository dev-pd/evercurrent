"""Bridge from the Slack connector to Celery: enqueue route_message for a persisted raw event."""

from __future__ import annotations

import uuid

import structlog

from evercurrent.jobs.celery_app import celery_app

log = structlog.get_logger(__name__)


def enqueue_route_message(*, raw_event_id: uuid.UUID) -> None:
    celery_app.send_task("evercurrent.route_message", args=[str(raw_event_id)])


SLACK_SEED_TASKS: tuple[str, ...] = ("evercurrent.route_message",)
