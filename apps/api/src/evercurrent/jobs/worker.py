"""Arq worker entrypoint.

Real task modules live under `tasks/`. They are registered here in the
order they were introduced through phases 2..7.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.cron import cron

from evercurrent.jobs.tasks.advance_day import advance_day
from evercurrent.jobs.tasks.enrich_messages import enrich_day
from evercurrent.jobs.tasks.extract_decisions import extract_decisions_for_day
from evercurrent.jobs.tasks.generate_digests import generate_all_digests
from evercurrent.jobs.tasks.ingest_doc import ingest_document
from evercurrent.jobs.tasks.refresh_today import refresh_today, synthesize_today_message
from evercurrent.jobs.tasks.regenerate_user_digest import regenerate_user_digest


async def heartbeat(_ctx: dict[str, Any]) -> str:
    """Smoke-test target for ops + CI."""
    return dt.datetime.now(dt.UTC).isoformat()


def _redis_settings_from_env() -> RedisSettings:
    url = os.environ.get("REDIS_URL")
    if url:
        return RedisSettings.from_dsn(url)
    return RedisSettings(host="redis", port=6379, database=0)


# Cron schedule. Demo cadence — production would key off Slack webhook
# arrival, not a wall-clock cron.
_REFRESH_MINUTES = set(range(0, 60, 2))  # every 2 minutes
_SYNTHESIZE_MINUTES = set(range(0, 60, 4))  # every 4 minutes


class WorkerSettings:
    """Arq WorkerSettings consumed by `arq evercurrent.jobs.worker.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [
        heartbeat,
        enrich_day,
        advance_day,
        extract_decisions_for_day,
        generate_all_digests,
        ingest_document,
        regenerate_user_digest,
        refresh_today,
        synthesize_today_message,
    ]
    cron_jobs: ClassVar[list[Any]] = [
        # Refresh today's digests every 2 minutes. Cheap: only regenerates
        # for the current day + current phase across all users (~8 calls).
        cron(refresh_today, minute=_REFRESH_MINUTES, second={5}, run_at_startup=True),
        # Generate one new message every 4 minutes to simulate the
        # continuous Slack stream a real deployment would receive.
        cron(synthesize_today_message, minute=_SYNTHESIZE_MINUTES, second={15}),
    ]
    redis_settings: ClassVar[RedisSettings] = _redis_settings_from_env()
    handle_signals: ClassVar[bool] = True
