from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.db.repositories import ProjectRepository
from evercurrent.db.repositories.read_stats import ReadStatsRepository
from evercurrent.timeline import TimelineProjection, build_timeline

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/{project_id}", response_model=TimelineProjection)
async def get_timeline(
    session: SessionDep,
    user: CurrentUserDep,
    project_id: uuid.UUID,
) -> TimelineProjection:
    _ = user
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )

    subsystems = await ReadStatsRepository(session).project_subsystems(project_id)
    return build_timeline(
        project_id=project.id,
        project_name=project.name,
        current_phase=project.current_phase,
        current_day=project.current_day,
        start_date=project.start_date,
        subsystems=subsystems,
    )
