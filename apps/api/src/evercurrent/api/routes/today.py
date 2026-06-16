from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.db.repositories import ProjectRepository
from evercurrent.db.repositories.read_stats import ReadStatsRepository

router = APIRouter(prefix="/api/v1/today", tags=["today"])


class TodayResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    project_id: uuid.UUID
    live_day: int
    live_date: str
    start_date: str
    phase: str
    phase_concerns: list[str]
    message_count: int
    last_message_at: str | None
    last_digest_generated_at: str | None


@router.get("", response_model=TodayResponse)
async def get_today(
    session: SessionDep,
    user: CurrentUserDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> TodayResponse:
    _ = user
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    activity = await ReadStatsRepository(session).recent_message_activity(project_id)

    last_digest_at = None

    return TodayResponse(
        project_id=project.id,
        live_day=project.current_day,
        live_date=project.date_for_day(project.current_day).isoformat(),
        start_date=project.start_date.isoformat(),
        phase=project.current_phase,
        phase_concerns=project.phase_concerns.get(project.current_phase, []),
        message_count=activity.count,
        last_message_at=activity.last_at.isoformat() if activity.last_at else None,
        last_digest_generated_at=last_digest_at.isoformat() if last_digest_at else None,
    )
