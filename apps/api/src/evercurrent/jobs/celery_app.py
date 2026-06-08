"""Celery app instance + beat schedule.

Celery runs the same async business logic as before; the
`celery_tasks` module wraps each `async def` impl in a thin sync task
via `asyncio.run`. Broker + result backend both use Redis (REDIS_URL).
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import schedule

_broker = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "evercurrent",
    broker=_broker,
    backend=_broker,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    result_expires=3600,
    task_default_retry_delay=5,
    task_default_max_retries=2,
    # Sub-minute schedules need `celery beat` running alongside worker.
    # `enqueue-due-digests` runs every minute and fans out one
    # `generate_digest_for_member` task per membership currently at
    # 08:00 local. Idempotency on `(member, day_index)` makes the
    # 5-minute window safe against double-fires.
    beat_schedule={
        "enqueue-due-digests": {
            "task": "evercurrent.enqueue_due_digests_now",
            "schedule": schedule(run_every=60.0),
        },
    },
    imports=("evercurrent.jobs.celery_tasks",),
)
