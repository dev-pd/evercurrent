"""Async impl behind a Celery task: advance the project simulation by one day."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.repositories import ProjectRepository
from evercurrent.db.session import session_scope
from evercurrent.jobs.tasks.enrich_messages import enrich_day

log = structlog.get_logger(__name__)


async def advance_day(ctx: dict[str, Any], project_id: str) -> dict[str, Any]:
    from evercurrent.decisions.extractor import extract_decisions_for_day
    from evercurrent.digest.generator import generate_all_digests_for_day

    project_uuid = uuid.UUID(project_id)
    async with session_scope() as session:
        projects = ProjectRepository(session)
        project = await projects.get_by_id(project_uuid)
        if project is None:
            msg = f"project {project_id} not found"
            raise LookupError(msg)
        new_day = project.current_day + 1
        await projects.set_current_day(project_uuid, new_day)
        await session.commit()

    log.info("simulation.advance.day_bumped", project_id=project_id, day=new_day)

    enrich_result = await enrich_day(ctx, project_id, new_day)
    decisions = await extract_decisions_for_day(project_uuid, new_day)
    digests = await generate_all_digests_for_day(project_uuid, new_day)

    log.info(
        "simulation.advance.done",
        project_id=project_id,
        day=new_day,
        tagged=enrich_result.get("tagged", 0),
        decisions=decisions,
        digests=digests,
    )
    return {"day": new_day, "tagged": enrich_result.get("tagged", 0), "digests": digests}
