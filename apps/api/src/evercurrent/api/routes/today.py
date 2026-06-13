from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.api.deps import SessionDep
from evercurrent.db.repositories import ProjectRepository

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
    project_id: Annotated[uuid.UUID, Query()],
) -> TodayResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    msg_count_row = await session.execute(
        text(
            "SELECT count(*) AS c, max(posted_at) AS last_at "
            "FROM messages "
            "WHERE project_id = :pid "
            "AND posted_at >= now() - interval '24 hours'"
        ),
        {"pid": str(project_id)},
    )
    msg_count, last_message_at = msg_count_row.one()

    last_digest_at = None

    return TodayResponse(
        project_id=project.id,
        live_day=project.current_day,
        live_date=project.date_for_day(project.current_day).isoformat(),
        start_date=project.start_date.isoformat(),
        phase=project.current_phase,
        phase_concerns=project.phase_concerns.get(project.current_phase, []),
        message_count=int(msg_count or 0),
        last_message_at=last_message_at.isoformat() if last_message_at else None,
        last_digest_generated_at=last_digest_at.isoformat() if last_digest_at else None,
    )
