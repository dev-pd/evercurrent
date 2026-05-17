"""Project routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from evercurrent.api.deps import SessionDep
from evercurrent.api.schemas import ChangePhaseRequest, ProjectResponse
from evercurrent.db.repositories import ProjectRepository

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_response(project: object) -> ProjectResponse:
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session: SessionDep) -> list[ProjectResponse]:
    projects = await ProjectRepository(session).list_all()
    return [ProjectResponse.model_validate(p.model_dump()) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, session: SessionDep) -> ProjectResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return ProjectResponse.model_validate(project.model_dump())


@router.post("/{project_id}/phase", response_model=ProjectResponse)
async def change_phase(
    project_id: uuid.UUID,
    payload: ChangePhaseRequest,
    session: SessionDep,
) -> ProjectResponse:
    from evercurrent.realtime import publish_event

    repo = ProjectRepository(session)
    project = await repo.set_phase(project_id, payload.phase)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    await session.commit()
    publish_event(project_id, "phase.changed", {"phase": payload.phase})
    return ProjectResponse.model_validate(project.model_dump())
