"""Today routes — exposes the live day + last cron refresh timestamp."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from evercurrent.api.deps import ArqPool, SessionDep
from evercurrent.api.schemas import GenerateDigestsResponse
from evercurrent.db.models import Digest as DigestModel
from evercurrent.db.models import Message as MessageModel
from evercurrent.db.repositories import ProjectRepository

router = APIRouter(prefix="/today", tags=["today"])


class TodayResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    project_id: uuid.UUID
    live_day: int
    phase: str
    message_count: int
    last_message_at: str | None
    last_digest_generated_at: str | None


@router.get("", response_model=TodayResponse)
async def get_today(
    session: SessionDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> TodayResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    msg_count_row = await session.execute(
        select(
            func.count(MessageModel.id),
            func.max(MessageModel.ts),
        ).where(
            MessageModel.project_id == project_id,
            MessageModel.day == project.current_day,
        ),
    )
    msg_count, last_message_at = msg_count_row.one()

    digest_row = await session.execute(
        select(func.max(DigestModel.generated_at)).where(
            DigestModel.project_id == project_id,
            DigestModel.day == project.current_day,
            DigestModel.phase == project.current_phase,
        ),
    )
    last_digest_at = digest_row.scalar_one_or_none()

    return TodayResponse(
        project_id=project.id,
        live_day=project.current_day,
        phase=project.current_phase,
        message_count=int(msg_count or 0),
        last_message_at=last_message_at.isoformat() if last_message_at else None,
        last_digest_generated_at=last_digest_at.isoformat() if last_digest_at else None,
    )


@router.post(
    "/refresh",
    response_model=GenerateDigestsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_refresh(
    arq: ArqPool,
    session: SessionDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> GenerateDigestsResponse:
    """Manually enqueue the refresh_today task.

    The worker also runs this on a 2-minute cron — this endpoint exists
    so the UI 'Refresh now' button doesn't have to wait for the next
    cron tick.
    """
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    job = await arq.enqueue_job(
        "refresh_today",
        project.name,
        _job_id=f"refresh_today:{project.id}:{project.current_day}:{project.current_phase}",
    )
    job_id = getattr(job, "job_id", str(uuid.uuid4()))
    return GenerateDigestsResponse(job_id=job_id, day=project.current_day)


@router.post(
    "/synthesize",
    response_model=GenerateDigestsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_synthesize(
    arq: ArqPool,
    session: SessionDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> GenerateDigestsResponse:
    """Enqueue a single synthetic 'today' message. Demo convenience."""
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    job = await arq.enqueue_job("synthesize_today_message", project.name)
    job_id = getattr(job, "job_id", str(uuid.uuid4()))
    return GenerateDigestsResponse(job_id=job_id, day=project.current_day)
