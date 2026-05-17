"""Arq task: advance the project simulation by one day."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.repositories import ProjectRepository
from evercurrent.db.session import session_scope
from evercurrent.jobs.tasks.enrich_messages import enrich_day

log = structlog.get_logger(__name__)


async def advance_day(ctx: dict[str, Any], project_id: str) -> dict[str, Any]:
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

    log.info("simulation.advance", project_id=project_id, day=new_day)
    await enrich_day(ctx, project_id, new_day)
    # extract_decisions_for_day and generate_all_digests wired in phase 6+7.
    return {"day": new_day}
