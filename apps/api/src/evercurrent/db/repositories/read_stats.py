"""The MessageActivity read-model + SQL for dashboard read stats (recent message
counts/recency)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import User as UserModel


class MessageActivity(BaseModel):
    model_config = ConfigDict(strict=True)

    count: int
    last_at: datetime | None


class ReadStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def recent_message_activity(self, project_id: uuid.UUID) -> MessageActivity:
        count, last_at = (
            await self._s.execute(
                text(
                    "SELECT count(*) AS c, max(posted_at) AS last_at "
                    "FROM messages "
                    "WHERE project_id = :pid "
                    "AND posted_at >= now() - interval '24 hours'"
                ),
                {"pid": str(project_id)},
            )
        ).one()
        return MessageActivity(count=int(count or 0), last_at=last_at)

    async def project_subsystems(self, project_id: uuid.UUID) -> list[str]:
        rows = await self._s.execute(
            select(func.distinct(func.unnest(UserModel.owned_subsystems))).where(
                UserModel.project_id == project_id,
            ),
        )
        return [s for (s,) in rows.all() if s]
