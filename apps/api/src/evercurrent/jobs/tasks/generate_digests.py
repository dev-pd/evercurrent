"""Arq task: score + generate digest for every user on a given day."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def generate_all_digests(
    _ctx: dict[str, Any],
    project_id: str,
    day: int,
) -> dict[str, Any]:
    from evercurrent.digest.generator import generate_all_digests_for_day

    project_uuid = uuid.UUID(project_id)
    count = await generate_all_digests_for_day(project_uuid, day)
    log.info("digest.generate_all.done", day=day, generated=count)
    return {"day": day, "generated": count}
