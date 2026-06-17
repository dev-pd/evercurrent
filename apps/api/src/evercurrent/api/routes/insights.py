from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.db.repositories.insights import InsightRepository

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


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
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
) -> list[ProactiveInsight]:
    payloads = await InsightRepository(session).list_payloads(org_id=user.org_id, limit=limit)
    return [ProactiveInsight(**payload) for payload in payloads]


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
    pid = await InsightRepository(session).get_first_project_id()
    if pid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no project")

    from evercurrent.jobs.celery_app import celery_app

    celery_app.send_task(
        "evercurrent.generate_eve_insight",
        kwargs={"project_id": str(pid), "org_id": str(user.org_id)},
    )
    log.info("eve.insight_enqueued", project_id=str(pid))
    return GenerateStarted(status="generating", project_id=pid)
