"""Feedback repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Feedback as FeedbackModel
from evercurrent.domain.digests import Feedback, FeedbackSignal


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_for_user(self, user_id: uuid.UUID, *, limit: int = 100) -> list[Feedback]:
        result = await self._s.execute(
            select(FeedbackModel)
            .where(FeedbackModel.user_id == user_id)
            .order_by(FeedbackModel.created_at.desc())
            .limit(limit),
        )
        return [Feedback.model_validate(r) for r in result.scalars()]

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
        signal: FeedbackSignal,
    ) -> Feedback:
        row = FeedbackModel(user_id=user_id, message_id=message_id, signal=int(signal))
        self._s.add(row)
        await self._s.flush()
        await self._s.refresh(row)
        return Feedback.model_validate(row)
