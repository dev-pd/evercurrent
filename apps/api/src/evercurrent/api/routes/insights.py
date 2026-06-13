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

import datetime as dt
import json
import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.eve import run_eve

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


def _normalize(emitted: dict[str, Any], *, insight_id: str, when: str) -> dict[str, Any]:
    """Fill required ProactiveInsight fields the agent may have omitted."""
    sources = [
        {
            "kind": s.get("kind", "slack"),
            "channel": s.get("channel"),
            "author": s.get("author"),
            "snippet": s.get("snippet", ""),
            "ts": s.get("ts"),
        }
        for s in (emitted.get("sources") or [])
    ]
    return {
        "id": insight_id,
        "req_id": emitted.get("req_id") or "—",
        "title": emitted.get("title") or "Untitled insight",
        "detected_at": when,
        "summary": emitted.get("summary") or "",
        "before": emitted.get("before") or [],
        "after": emitted.get("after") or [],
        "affected_subsystems": emitted.get("affected_subsystems") or [],
        "conflicts": emitted.get("conflicts") or [],
        "sources": sources,
        "suggested_action": emitted.get("suggested_action")
        or {"label": "Review with the team", "invitees": [], "description": ""},
        "impact_summary": emitted.get("impact_summary") or {},
    }


@router.get("", response_model=list[ProactiveInsight])
async def list_insights(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[ProactiveInsight]:
    """Stored Eve insights, most recent first. RLS scopes to the caller's org."""
    _ = user
    rows = (
        await session.execute(
            text("SELECT payload FROM insights ORDER BY created_at DESC LIMIT :n"),
            {"n": limit},
        )
    ).all()
    return [ProactiveInsight(**row[0]) for row in rows]


@router.post("/generate", response_model=ProactiveInsight)
async def generate_insight(session: SessionDep, user: CurrentUserDep) -> ProactiveInsight:
    """Run the Eve agent over recent activity, store + return the insight."""
    project = (await session.execute(text("SELECT id FROM projects LIMIT 1"))).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no project")

    emitted = await run_eve(session, project_id=uuid.UUID(str(project[0])))
    if emitted is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Eve produced no insight",
        )

    insight_id = str(uuid.uuid4())
    when = dt.datetime.now(dt.UTC).isoformat()
    payload = _normalize(emitted, insight_id=insight_id, when=when)
    insight = ProactiveInsight(**payload)  # validate before storing

    # Eve's read tools share this session; a failed read can abort the tx.
    # Reads are throwaway, so roll back to a clean tx before persisting.
    await session.rollback()
    await session.execute(
        text(
            "INSERT INTO insights (org_id, payload) VALUES (:org, CAST(:p AS jsonb))",
        ),
        {"org": str(user.org_id), "p": json.dumps(payload)},
    )
    await session.commit()
    log.info("eve.insight_stored", insight_id=insight_id, title=insight.title)
    return insight
