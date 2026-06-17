"""Celery app singleton: Redis broker/backend wiring + the beat schedule for the
recurring digest/insight/sync jobs."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import schedule

from evercurrent.jobs import metrics_server as _metrics_server  # noqa: F401  registers worker_init

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
    beat_schedule={
        "enqueue-due-digests": {
            "task": "evercurrent.enqueue_due_digests_now",
            "schedule": schedule(run_every=60.0),
        },
        "emit-demo-chatter": {
            "task": "evercurrent.emit_demo_chatter",
            "schedule": schedule(
                run_every=float(os.environ.get("DEMO_CHATTER_INTERVAL_SECONDS", "600")),
            ),
        },
    },
    imports=("evercurrent.jobs.celery_tasks",),
)
