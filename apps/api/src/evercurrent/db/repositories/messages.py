"""Message + tag repository."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from evercurrent.db.models import (
    Channel as ChannelModel,
)
from evercurrent.db.models import (
    Message as MessageModel,
)
from evercurrent.db.models import (
    MessageTag as MessageTagModel,
)
from evercurrent.db.models import (
    User as UserModel,
)
from evercurrent.domain.messages import EnrichedMessage, Message, MessageTag, Urgency


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        row = await self._s.get(MessageModel, message_id)
        return Message.model_validate(row) if row else None

    async def get_enriched(self, message_id: uuid.UUID) -> EnrichedMessage | None:
        stmt = (
            select(MessageModel)
            .options(
                selectinload(MessageModel.tags),
                joinedload(MessageModel.channel),
                joinedload(MessageModel.author),
            )
            .where(MessageModel.id == message_id)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return EnrichedMessage(
            message=Message.model_validate(row),
            tag=MessageTag.model_validate(row.tags) if row.tags else None,
            author_username=row.author.username,
            channel_name=row.channel.name,
        )

    async def list_for_day(
        self,
        project_id: uuid.UUID,
        day: int,
        *,
        with_tags: bool = False,
    ) -> list[EnrichedMessage]:
        stmt = (
            select(MessageModel)
            .options(
                joinedload(MessageModel.author),
                joinedload(MessageModel.channel),
            )
            .where(MessageModel.project_id == project_id, MessageModel.day == day)
            .order_by(MessageModel.ts)
        )
        if with_tags:
            stmt = stmt.options(selectinload(MessageModel.tags))
        result = await self._s.execute(stmt)
        rows = list(result.scalars().unique())
        return [
            EnrichedMessage(
                message=Message.model_validate(r),
                tag=MessageTag.model_validate(r.tags) if (with_tags and r.tags) else None,
                author_username=r.author.username,
                channel_name=r.channel.name,
            )
            for r in rows
        ]

    async def count_for_day(self, project_id: uuid.UUID, day: int) -> int:
        result = await self._s.execute(
            select(MessageModel.id).where(
                MessageModel.project_id == project_id,
                MessageModel.day == day,
            ),
        )
        return len(list(result.scalars()))

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        channel_id: uuid.UUID,
        author_id: uuid.UUID,
        day: int,
        text: str,
        ts: dt.datetime,
        thread_root_id: uuid.UUID | None = None,
        reactions: dict[str, int] | None = None,
    ) -> Message:
        row = MessageModel(
            project_id=project_id,
            channel_id=channel_id,
            author_id=author_id,
            day=day,
            text=text,
            ts=ts,
            thread_root_id=thread_root_id,
            reactions=reactions or {},
        )
        self._s.add(row)
        await self._s.flush()
        await self._s.refresh(row)
        return Message.model_validate(row)

    async def get_thread(self, root_message_id: uuid.UUID) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(
                (MessageModel.id == root_message_id)
                | (MessageModel.thread_root_id == root_message_id),
            )
            .order_by(MessageModel.ts)
        )
        result = await self._s.execute(stmt)
        return [Message.model_validate(r) for r in result.scalars()]

    async def search_text(
        self,
        project_id: uuid.UUID,
        query: str,
        *,
        channel_name: str | None = None,
        author_username: str | None = None,
        topic: str | None = None,
        since: dt.datetime | None = None,
        limit: int = 10,
    ) -> list[EnrichedMessage]:
        stmt = (
            select(MessageModel)
            .options(
                joinedload(MessageModel.author),
                joinedload(MessageModel.channel),
                selectinload(MessageModel.tags),
            )
            .where(MessageModel.project_id == project_id)
            .where(MessageModel.text.ilike(f"%{query}%"))
        )
        if channel_name:
            stmt = stmt.join(ChannelModel).where(ChannelModel.name == channel_name)
        if author_username:
            stmt = stmt.join(UserModel).where(UserModel.username == author_username)
        if since:
            stmt = stmt.where(MessageModel.ts >= since)
        if topic:
            stmt = stmt.join(MessageTagModel).where(MessageTagModel.topic == topic)
        stmt = stmt.order_by(MessageModel.ts.desc()).limit(limit)
        result = await self._s.execute(stmt)
        rows = list(result.scalars().unique())
        return [
            EnrichedMessage(
                message=Message.model_validate(r),
                tag=MessageTag.model_validate(r.tags) if r.tags else None,
                author_username=r.author.username,
                channel_name=r.channel.name,
            )
            for r in rows
        ]

    async def upsert_tag(
        self,
        *,
        message_id: uuid.UUID,
        topic: str,
        urgency: Urgency,
        affected_roles: list[str],
        entities: list[str],
        raw_tag: dict[str, object] | None = None,
    ) -> MessageTag:
        stmt = (
            pg_insert(MessageTagModel)
            .values(
                message_id=message_id,
                topic=topic,
                urgency=urgency.value,
                affected_roles=affected_roles,
                entities=entities,
                raw_tag=raw_tag or {},
            )
            .on_conflict_do_update(
                index_elements=[MessageTagModel.message_id],
                set_={
                    "topic": topic,
                    "urgency": urgency.value,
                    "affected_roles": affected_roles,
                    "entities": entities,
                    "raw_tag": raw_tag or {},
                },
            )
            .returning(MessageTagModel)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one()
        return MessageTag.model_validate(row)
