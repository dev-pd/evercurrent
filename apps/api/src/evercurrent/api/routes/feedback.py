"""Feedback routes — thumbs up/down updates per-user topic weights."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from evercurrent.api.deps import SessionDep
from evercurrent.api.schemas import FeedbackRequest, FeedbackResponse
from evercurrent.db.repositories import FeedbackRepository, MessageRepository, UserRepository
from evercurrent.domain.digests import FeedbackSignal

router = APIRouter(prefix="/feedback", tags=["feedback"])

_FEEDBACK_DELTA = 1.0


@router.post("", response_model=FeedbackResponse)
async def post_feedback(payload: FeedbackRequest, session: SessionDep) -> FeedbackResponse:
    users = UserRepository(session)
    msgs = MessageRepository(session)
    fb = FeedbackRepository(session)

    user = await users.get_by_id(payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    enriched = await msgs.get_enriched(payload.message_id)
    if enriched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message not found")

    topic = payload.topic or (enriched.tag.topic if enriched.tag else None)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message has no tag yet; pass `topic` explicitly",
        )

    signal = FeedbackSignal(payload.signal)
    await fb.create(user_id=user.id, message_id=enriched.message.id, signal=signal)
    delta = _FEEDBACK_DELTA * int(signal)
    updated = await users.bump_topic_weight(user.id, topic, delta)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    await session.commit()
    return FeedbackResponse(user_id=updated.id, topic_weights=updated.topic_weights)
