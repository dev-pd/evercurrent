from __future__ import annotations

import json

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.focus import FocusTopic, compute_focus

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/focus", tags=["focus"])


async def _load_and_compute(session: SessionDep, membership_id: str) -> list[FocusTopic]:
    member = (
        (
            await session.execute(
                text(
                    "SELECT eng_role, owned_subsystems, topic_weights "
                    "FROM org_memberships WHERE id = :id",
                ),
                {"id": membership_id},
            )
        )
        .mappings()
        .first()
    )
    if member is None:
        return []

    project = (
        (
            await session.execute(
                text("SELECT current_phase, phase_concerns FROM projects LIMIT 1"),
            )
        )
        .mappings()
        .first()
    )
    phase_concerns: list[str] = []
    if project is not None:
        phase_concerns = list((project["phase_concerns"] or {}).get(project["current_phase"], []))

    return compute_focus(
        eng_role=member["eng_role"],
        owned_subsystems=list(member["owned_subsystems"] or []),
        phase_concerns=phase_concerns,
        topic_weights=dict(member["topic_weights"] or {}),
    )


@router.get("", response_model=list[FocusTopic])
async def get_focus(session: SessionDep, user: CurrentUserDep) -> list[FocusTopic]:
    return await _load_and_compute(session, str(user.membership_id))


class FocusSignal(BaseModel):
    model_config = ConfigDict(strict=True)

    topic: str
    delta: float


@router.post("/signal", response_model=list[FocusTopic])
async def post_focus_signal(
    payload: FocusSignal,
    session: SessionDep,
    user: CurrentUserDep,
) -> list[FocusTopic]:
    mid = str(user.membership_id)
    row = (
        (
            await session.execute(
                text("SELECT topic_weights FROM org_memberships WHERE id = :id"),
                {"id": mid},
            )
        )
        .mappings()
        .first()
    )
    weights: dict[str, float] = dict(row["topic_weights"] or {}) if row else {}
    key = payload.topic.strip().lower()
    weights[key] = max(-2.0, min(2.0, weights.get(key, 0.0) + payload.delta))

    await session.execute(
        text("UPDATE org_memberships SET topic_weights = CAST(:w AS jsonb) WHERE id = :id"),
        {"w": json.dumps(weights), "id": mid},
    )
    await session.commit()
    log.info("focus.signal", membership_id=mid, topic=key, delta=payload.delta)
    return await _load_and_compute(session, mid)
