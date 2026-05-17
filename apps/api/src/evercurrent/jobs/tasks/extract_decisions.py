"""Arq task: extract decisions from a day's messages.

The implementation lives in `evercurrent.decisions.extractor`. This module
wraps it for Arq scheduling.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def extract_decisions_for_day(
    _ctx: dict[str, Any],
    project_id: str,
    day: int,
) -> dict[str, Any]:
    from evercurrent.decisions.extractor import extract_decisions_for_day as _do

    project_uuid = uuid.UUID(project_id)
    count = await _do(project_uuid, day)
    log.info("decisions.extract.done", day=day, extracted=count)
    return {"day": day, "extracted": count}
