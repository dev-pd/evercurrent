"""Realtime pub/sub bridge between Celery workers and the API.

Celery tasks call `publish_event(...)` over a sync Redis client to push
a JSON event onto a per-project channel. The FastAPI `/events` SSE
endpoint subscribes to that channel via an async Redis client and
relays the events out to the browser. EventSource on the frontend
swaps the polling heartbeat for server-pushed updates.

Channel: `events:{project_id}`
Events: `digest.updated`, `message.synthesized`, `phase.changed`,
        `decisions.updated`
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import redis as redis_sync
import structlog

log = structlog.get_logger(__name__)


def _channel(project_id: uuid.UUID | str) -> str:
    return f"events:{project_id}"


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://redis:6379/0")


def publish_event(
    project_id: uuid.UUID | str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish a JSON event to a project's realtime channel.

    Sync — safe to call from Celery task bodies. No-op on connection
    errors so a transient Redis blip never fails a task.
    """
    body = json.dumps({"type": event_type, **(payload or {})}, default=str)
    try:
        client = redis_sync.Redis.from_url(_redis_url())
        client.publish(_channel(project_id), body)
        client.close()
    except redis_sync.RedisError as exc:
        log.warning("realtime.publish_failed", channel=_channel(project_id), error=str(exc))
