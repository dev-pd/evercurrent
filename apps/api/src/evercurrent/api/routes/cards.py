from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.cards import repository as cards_repo
from evercurrent.cards.schemas import (
    CardFeedbackPayload,
    CardListItem,
    CardResponse,
)
from evercurrent.db.repositories.memberships import MembershipRepository

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CardListItem])
async def list_cards(
    session: SessionDep,
    _user: CurrentUserDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 50,
) -> list[CardListItem]:
    return await cards_repo.list_cards(
        session,
        project_id=project_id,
        kind=kind,
        status=status_filter,
        limit=limit,
    )


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: uuid.UUID,
    session: SessionDep,
    _user: CurrentUserDep,
) -> CardResponse:
    card = await cards_repo.get_card(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="card not found",
        )
    return card


_FEEDBACK_DELTA = 1.0


@router.post("/{card_id}/feedback")
async def post_card_feedback(
    card_id: uuid.UUID,
    payload: CardFeedbackPayload,
    session: SessionDep,
    user: CurrentUserDep,
) -> dict[str, object]:
    card = await cards_repo.get_card(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="card not found",
        )

    topic = payload.topic or _infer_topic(card.affected_subsystems)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="card has no topic; pass `topic` explicitly",
        )

    delta = _FEEDBACK_DELTA * int(payload.signal)
    updated = await _bump_membership_topic_weight(
        session,
        membership_id=user.membership_id,
        topic=topic,
        delta=delta,
    )
    await session.commit()

    return {
        "membership_id": str(user.membership_id),
        "topic": topic,
        "weight": updated,
    }


def _infer_topic(subsystems: list[str]) -> str | None:
    if not subsystems:
        return None
    return subsystems[0]


async def _bump_membership_topic_weight(
    session: SessionDep,
    *,
    membership_id: uuid.UUID,
    topic: str,
    delta: float,
) -> float:
    try:
        updated = await MembershipRepository(session).bump_topic_weight(
            membership_id,
            topic=topic,
            delta=delta,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "cards.feedback.weight_bump_failed",
            membership_id=str(membership_id),
            topic=topic,
            error=str(exc),
        )
        return delta
    return updated if updated is not None else delta
