"""Arq worker entrypoint.

Phase 0.2 scope: a bootable worker with a single `heartbeat` task. Real
tasks (enrich_messages, generate_digests, extract_decisions, advance_day,
ingest_doc) are appended to `WorkerSettings.functions` as later phases
implement them.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, ClassVar

from arq.connections import RedisSettings


async def heartbeat(_ctx: dict[str, Any]) -> str:
    """Return an ISO timestamp. Smoke-test target for ops + CI."""
    return dt.datetime.now(dt.UTC).isoformat()


def _redis_settings_from_env() -> RedisSettings:
    url = os.environ.get("REDIS_URL")
    if url:
        return RedisSettings.from_dsn(url)
    return RedisSettings(host="redis", port=6379, database=0)


class WorkerSettings:
    """Arq WorkerSettings consumed by `arq evercurrent.jobs.worker.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [heartbeat]
    redis_settings: ClassVar[RedisSettings] = _redis_settings_from_env()
    handle_signals: ClassVar[bool] = True
