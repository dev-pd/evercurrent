from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.db.repositories.focus_repo import FocusRepository
from evercurrent.focus import FocusTopic, compute_focus

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/focus", tags=["focus"])


async def _load_and_compute(session: SessionDep, membership_id: str) -> list[FocusTopic]:
    repo = FocusRepository(session)
    inputs = await repo.load_inputs(membership_id)
    if inputs is None:
        return []
    return compute_focus(
        eng_role=inputs.eng_role,
        owned_subsystems=inputs.owned_subsystems,
        phase_concerns=await repo.phase_concerns(),
        topic_weights=inputs.topic_weights,
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
    repo = FocusRepository(session)
    weights = await repo.get_topic_weights(mid)
    key = payload.topic.strip().lower()
    weights[key] = max(-2.0, min(2.0, weights.get(key, 0.0) + payload.delta))

    await repo.set_topic_weights(mid, weights)
    await session.commit()
    log.info("focus.signal", membership_id=mid, topic=key, delta=payload.delta)
    return await _load_and_compute(session, mid)
