from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.auth.deps import CurrentUserDep, SessionDep

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


class SpecSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)
    label: str
    value: str


class Conflict(BaseModel):
    model_config = ConfigDict(strict=True)
    subsystem: str
    severity: str
    title: str
    detail: str
    impact: str


class InsightSource(BaseModel):
    model_config = ConfigDict(strict=True)
    kind: str
    channel: str | None = None
    author: str | None = None
    snippet: str
    ts: str | None = None


class SuggestedAction(BaseModel):
    model_config = ConfigDict(strict=True)
    label: str
    invitees: list[str]
    description: str


class ProactiveInsight(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    req_id: str
    title: str
    detected_at: str
    summary: str
    before: list[SpecSnapshot]
    after: list[SpecSnapshot]
    affected_subsystems: list[str]
    conflicts: list[Conflict]
    sources: list[InsightSource]
    suggested_action: SuggestedAction
    impact_summary: dict[str, str]


@router.get("", response_model=list[ProactiveInsight])
async def list_insights(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[ProactiveInsight]:
    rows = (
        await session.execute(
            text(
                "SELECT payload FROM insights WHERE org_id = :org "
                "ORDER BY created_at DESC LIMIT :n",
            ),
            {"org": str(user.org_id), "n": limit},
        )
    ).all()
    return [ProactiveInsight(**row[0]) for row in rows]


class GenerateStarted(BaseModel):
    model_config = ConfigDict(strict=True)
    status: str
    project_id: uuid.UUID


@router.post(
    "/generate",
    response_model=GenerateStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_insight(session: SessionDep, user: CurrentUserDep) -> GenerateStarted:
    project = (await session.execute(text("SELECT id FROM projects LIMIT 1"))).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no project")
    pid = uuid.UUID(str(project[0]))

    from evercurrent.jobs.celery_app import celery_app

    celery_app.send_task(
        "evercurrent.generate_eve_insight",
        kwargs={"project_id": str(pid), "org_id": str(user.org_id)},
    )
    log.info("eve.insight_enqueued", project_id=str(pid))
    return GenerateStarted(status="generating", project_id=pid)
