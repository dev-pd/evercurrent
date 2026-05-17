"""Async impl behind a Celery task: regenerate one user's digest for (day, phase).

Per-user, idempotent — keyed on (project_id, user_id, day, phase). The
Celery wrapper publishes a `digest.updated` SSE event on success so the
dashboard refetches without polling.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def regenerate_user_digest(
    _ctx: dict[str, Any],
    project_id: str,
    user_id: str,
    day: int,
    phase: str | None = None,
) -> dict[str, Any]:
    from evercurrent.digest.generator import generate_digest_for_user

    project_uuid = uuid.UUID(project_id)
    user_uuid = uuid.UUID(user_id)
    content = await generate_digest_for_user(
        project_id=project_uuid,
        user_id=user_uuid,
        day=day,
        phase=phase,
    )
    log.info(
        "digest.regenerate_user.done",
        project_id=project_id,
        user_id=user_id,
        day=day,
        phase=phase,
        wrote=content is not None,
    )
    return {"project_id": project_id, "user_id": user_id, "day": day, "phase": phase}
