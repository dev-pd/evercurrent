"""Celery enqueue helper owned by the Slack connector.

The events webhook persists a `raw_events` row then enqueues the real
`evercurrent.route_message` task (raw_event -> messages + message_tags +
score + card), which is registered in `jobs/celery_tasks.py` and runs in
the worker. We enqueue **by name** so this module never re-registers the
task (a previous stub here collided with the real one).
"""

from __future__ import annotations

import uuid

import structlog

from evercurrent.jobs.celery_app import celery_app

log = structlog.get_logger(__name__)


def enqueue_route_message(*, raw_event_id: uuid.UUID) -> None:
    """Enqueue the real route_message pipeline task by name."""
    celery_app.send_task("evercurrent.route_message", args=[str(raw_event_id)])


SLACK_SEED_TASKS: tuple[str, ...] = ("evercurrent.route_message",)
