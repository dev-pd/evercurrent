"""Proactive insight routes — the Eve agent surface.

Returns structured insights about requirement changes, decisions, and
their downstream impact (cost / schedule / revenue). For the demo the
insights are seeded; in production they're synthesized from message
stream + RAG over specs by the same LLM tier that drives the digest.

Each insight has:

- A change summary (what moved)
- Before / after spec snapshot
- Affected subsystems
- Conflicts: weight, thermal, cost, schedule, revenue
- Suggested action ("invite affected teams") with the persona list
- Source citations back to messages / docs
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Query
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


# Demo insights — believable, reference real seed corpus content
_DEMO_INSIGHTS: list[ProactiveInsight] = [
    ProactiveInsight(
        id="ins-req-245",
        req_id="REQ-245",
        title="Motor torque requirement increased 15 Nm → 22 Nm",
        detected_at="2026-06-07T09:14:00Z",
        summary=(
            "Customer escalated continuous-torque requirement after their "
            "small-batch field trial. Change crosses chassis, power, and "
            "thermal subsystems and exceeds the design envelope on two."
        ),
        before=[
            SpecSnapshot(label="Continuous torque", value="15 Nm"),
            SpecSnapshot(label="Peak torque", value="20 Nm"),
            SpecSnapshot(label="Compliance margin", value="13%"),
        ],
        after=[
            SpecSnapshot(label="Continuous torque", value="22 Nm"),
            SpecSnapshot(label="Peak torque", value="28 Nm"),
            SpecSnapshot(label="Compliance margin", value="-4%"),
        ],
        affected_subsystems=["chassis", "power", "qa"],
        conflicts=[
            Conflict(
                subsystem="chassis",
                severity="critical",
                title="System weight likely > 10 kg upper limit",
                detail=(
                    "Bigger motor + heavier bracket pushes estimated mass to "
                    "10.4 kg. Customer spec hard limit is 10.0 kg."
                ),
                impact="+1.4 kg",
            ),
            Conflict(
                subsystem="power",
                severity="warn",
                title="Thermal envelope reduced",
                detail=(
                    "Higher torque means higher I²R losses; regulator U7 was "
                    "already 78°C at peak under prior spec."
                ),
                impact="+12°C peak",
            ),
            Conflict(
                subsystem="supply_chain",
                severity="warn",
                title="Steel housing machining adds cost + lead time",
                detail=(
                    "Aluminum bracket no longer adequate. Switching to steel "
                    "raises BOM cost and AlumWest is not a steel supplier."
                ),
                impact="+$3.40/unit · +2 wk",
            ),
        ],
        sources=[
            InsightSource(
                kind="slack",
                channel="#general",
                author="Raj Mehta",
                snippet=(
                    "Customer call this morning: they're moving their launch "
                    "window forward by 3 weeks. New target FCS: Sep 15."
                ),
                ts="2026-06-05T15:02:00Z",
            ),
            InsightSource(
                kind="slack",
                channel="#mech-design",
                author="Sarah Chen",
                snippet=(
                    "Heads up — if AlumWest CTE shifts more than 5% we'll "
                    "need to revisit the rib pitch on ECO-178."
                ),
                ts="2026-06-04T11:31:00Z",
            ),
            InsightSource(
                kind="doc",
                channel="REQ-245.pdf",
                author=None,
                snippet=(
                    "The drive motor shall provide a minimum continuous "
                    "torque of 22 Nm at 2000 RPM. Peak torque shall not "
                    "exceed 28 Nm for safety compliance."
                ),
                ts=None,
            ),
        ],
        suggested_action=SuggestedAction(
            label="Invite affected teams",
            invitees=["Sarah Chen", "Dan Okafor", "Lin Park", "Mei Tanaka"],
            description=(
                "Open a thread tagging mech, electrical, qa, and supply chain "
                "with the change diff + conflict list so they can respond "
                "before the design freeze on Friday."
            ),
        ),
        impact_summary={
            "cost": "+$3.40/unit",
            "schedule": "+2 wk if confirmed",
            "revenue_at_risk": "$182k Q3 if FCS slips",
        },
    ),
    ProactiveInsight(
        id="ins-eco-187",
        req_id="ECO-187",
        title="I²C glitch fix: add 22 pF cap on SDA",
        detected_at="2026-06-06T17:48:00Z",
        summary=(
            "Validated bench fix for the BLE-radio induced I²C glitch. "
            "Lands in PVT1 with the stencil recut, no schedule impact."
        ),
        before=[
            SpecSnapshot(label="Glitch duration", value="~200 ns"),
            SpecSnapshot(label="I²C spec margin", value="-3 dB"),
        ],
        after=[
            SpecSnapshot(label="Glitch duration", value="<50 ns"),
            SpecSnapshot(label="I²C spec margin", value="+18 dB"),
        ],
        affected_subsystems=["power", "firmware"],
        conflicts=[
            Conflict(
                subsystem="manufacturing",
                severity="info",
                title="Stencil recut already in flight for ECO-185",
                detail=(
                    "Rolling 187 in adds no new tooling work. Anna confirmed."
                ),
                impact="0 wk · $0",
            ),
        ],
        sources=[
            InsightSource(
                kind="slack",
                channel="#electrical",
                author="Dan Okafor",
                snippet=(
                    "RISK-22 update: 22pF cap on SDA pulls the glitch under "
                    "50ns, well inside I2C spec. ECO-187 to add the cap."
                ),
                ts="2026-06-06T16:11:00Z",
            ),
        ],
        suggested_action=SuggestedAction(
            label="Close RISK-22",
            invitees=["Dan Okafor", "Anna Volkov", "Lin Park"],
            description=(
                "RISK-22 was the original glitch — the ECO closes it. "
                "Notify reviewers + flip RISK status to closed."
            ),
        ),
        impact_summary={
            "cost": "$0",
            "schedule": "0 wk",
            "revenue_at_risk": "0",
        },
    ),
]


@router.get("", response_model=list[ProactiveInsight])
async def list_insights(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[ProactiveInsight]:
    """Proactive insights for the current member. Seed-driven for the demo."""
    _ = user  # RLS already applied by deps
    _ = session
    return _DEMO_INSIGHTS[:limit]


@router.get("/{insight_id}", response_model=ProactiveInsight)
async def get_insight(
    session: SessionDep,
    user: CurrentUserDep,
    insight_id: str,
) -> ProactiveInsight:
    _ = user
    _ = session
    for ins in _DEMO_INSIGHTS:
        if ins.id == insight_id:
            return ins
    # Fallback: query messages to demonstrate hydration even without seed match
    rows = (
        await session.execute(
            text("SELECT id FROM messages LIMIT 1"),
        )
    ).first()
    _ = rows
    raise ValueError(f"insight {insight_id} not found")
