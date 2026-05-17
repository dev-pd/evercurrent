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


# Cron cadence. Production replaces synthesize with a Slack webhook
# listener and keeps refresh as a 30s backstop.
_EVERY_MINUTE = set(range(60))
_REFRESH_SECONDS = {0, 30}  # refresh_today fires twice a minute
_SYNTHESIZE_SECONDS = {15}   # synthesize fires once a minute


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
        # Every 30s: enrich any new inbound messages, regenerate digests
        # for today's day + current phase, re-extract decisions. ~8 LLM
        # calls per tick.
        cron(
            refresh_today,
            minute=_EVERY_MINUTE,
            second=_REFRESH_SECONDS,
            run_at_startup=True,
        ),
        # Every 60s: synth a small batch of phase-scoped messages so the
        # UI shows live inbound traffic.
        cron(
            synthesize_today_message,
            minute=_EVERY_MINUTE,
            second=_SYNTHESIZE_SECONDS,
        ),
    ]
    redis_settings: ClassVar[RedisSettings] = _redis_settings_from_env()
    handle_signals: ClassVar[bool] = True
