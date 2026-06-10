"""Proactive insight routes — the Eve agent surface.

Returns structured insights about requirement changes, decisions, and
their downstream impact (cost / schedule / revenue). Insights are
synthesized from the message stream + RAG over specs by the same LLM
tier that drives the digest. No insight generation is wired yet, so the
endpoints return an empty set until that pipeline lands.

Each insight has:

- A change summary (what moved)
- Before / after spec snapshot
- Affected subsystems
- Conflicts: weight, thermal, cost, schedule, revenue
- Suggested action ("invite affected teams") with the persona list
- Source citations back to messages / docs
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

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
    severity: str  # "info" | "warn" | "critical"
    title: str
    detail: str
    impact: str  # short impact line e.g. "+1.4 kg" / "+2 weeks" / "$3.40/unit"


class InsightSource(BaseModel):
    model_config = ConfigDict(strict=True)
    kind: str  # "slack" | "doc"
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
    impact_summary: dict[str, str]  # cost, schedule, revenue


@router.get("", response_model=list[ProactiveInsight])
async def list_insights(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[ProactiveInsight]:
    """Proactive insights for the current member.

    Insight synthesis is not wired yet; returns an empty set until the
    generation pipeline (message stream + RAG over specs) lands.
    """
    _ = (session, user, limit)  # RLS already applied by deps
    return []


@router.get("/{insight_id}", response_model=ProactiveInsight)
async def get_insight(
    session: SessionDep,
    user: CurrentUserDep,
    insight_id: str,
) -> ProactiveInsight:
    _ = (session, user)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"insight {insight_id} not found",
    )
