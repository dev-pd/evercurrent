from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Channel as ChannelModel
from evercurrent.domain.projects import Channel


class ChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, channel_id: uuid.UUID) -> Channel | None:
        row = await self._s.get(ChannelModel, channel_id)
        return Channel.model_validate(row) if row else None

    async def get_by_name(self, project_id: uuid.UUID, name: str) -> Channel | None:
        result = await self._s.execute(
            select(ChannelModel).where(
                ChannelModel.project_id == project_id,
                ChannelModel.name == name,
            ),
        )
        row = result.scalar_one_or_none()
        return Channel.model_validate(row) if row else None

    async def list_for_project(self, project_id: uuid.UUID) -> list[Channel]:
        result = await self._s.execute(
            select(ChannelModel)
            .where(ChannelModel.project_id == project_id)
            .order_by(ChannelModel.name),
        )
        return [Channel.model_validate(r) for r in result.scalars()]

    async def upsert(
        self,
        *,
        project_id: uuid.UUID,
        name: str,
        description: str | None = None,
    ) -> Channel:
        stmt = (
            pg_insert(ChannelModel)
            .values(project_id=project_id, name=name, description=description)
            .on_conflict_do_update(
                index_elements=[ChannelModel.project_id, ChannelModel.name],
                set_={"description": description},
            )
            .returning(ChannelModel)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one()
        return Channel.model_validate(row)
