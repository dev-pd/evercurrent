from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status

from evercurrent.api.schemas import (
    ChangePhaseRequest,
    CreateProjectRequest,
    ProjectResponse,
)
from evercurrent.auth.deps import AdminUserDep, CurrentUserDep, SessionDep
from evercurrent.db.repositories import ProjectRepository

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_response(project: object) -> ProjectResponse:
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session: SessionDep, user: CurrentUserDep) -> list[ProjectResponse]:
    _ = user
    projects = await ProjectRepository(session).list_all()
    return [ProjectResponse.model_validate(p.model_dump()) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectRequest,
    session: SessionDep,
    user: AdminUserDep,
) -> ProjectResponse:
    existing = await ProjectRepository(session).list_all()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="one project per organization (multi-project routing is the next step)",
        )
    current_day = max(1, (dt.datetime.now(dt.UTC).date() - payload.start_date).days)
    project = await ProjectRepository(session).create(
        org_id=user.org_id,
        name=payload.name,
        current_phase=payload.current_phase,
        start_date=payload.start_date,
        current_day=current_day,
        phase_concerns=payload.phase_concerns,
    )
    await session.commit()
    return ProjectResponse.model_validate(project.model_dump())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUserDep,
) -> ProjectResponse:
    _ = user
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return ProjectResponse.model_validate(project.model_dump())


@router.post("/{project_id}/phase", response_model=ProjectResponse)
async def change_phase(
    project_id: uuid.UUID,
    payload: ChangePhaseRequest,
    session: SessionDep,
    user: AdminUserDep,
) -> ProjectResponse:
    _ = user
    from evercurrent.realtime import publish_event

    repo = ProjectRepository(session)
    project = await repo.set_phase(project_id, payload.phase)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    await session.commit()
    publish_event(project_id, "phase.changed", {"phase": payload.phase})
    return ProjectResponse.model_validate(project.model_dump())
