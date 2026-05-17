"""Simulation routes — advance day + status."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from evercurrent.api.deps import ArqPool, SessionDep
from evercurrent.api.schemas import GenerateDigestsResponse, SimulationStatusResponse
from evercurrent.db.repositories import ProjectRepository

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/status", response_model=SimulationStatusResponse)
async def simulation_status(
    session: SessionDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> SimulationStatusResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return SimulationStatusResponse(current_day=project.current_day)


@router.post(
    "/advance-day",
    response_model=GenerateDigestsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def advance_day(
    arq: ArqPool,
    session: SessionDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> GenerateDigestsResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    next_day = project.current_day + 1
    job = await arq.enqueue_job("advance_day", str(project_id))
    job_id = getattr(job, "job_id", str(uuid.uuid4()))
    return GenerateDigestsResponse(job_id=job_id, day=next_day)
