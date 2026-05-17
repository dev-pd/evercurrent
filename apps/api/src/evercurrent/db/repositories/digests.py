"""Digest repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Digest as DigestModel
from evercurrent.domain.digests import Digest


class DigestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        user_id: uuid.UUID,
        day: int,
        *,
        phase: str | None = None,
    ) -> Digest | None:
        """Return the digest for (user, day, phase).

        If `phase` is None, returns the most recently generated row for the
        (user, day) cell — useful as a fallback in legacy reads.
        """
        stmt = select(DigestModel).where(
            DigestModel.user_id == user_id,
            DigestModel.day == day,
        )
        if phase is not None:
            stmt = stmt.where(DigestModel.phase == phase)
        else:
            stmt = stmt.order_by(DigestModel.generated_at.desc())
        result = await self._s.execute(stmt.limit(1))
        row = result.scalar_one_or_none()
        return Digest.model_validate(row) if row else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[Digest]:
        result = await self._s.execute(
            select(DigestModel).where(DigestModel.user_id == user_id).order_by(DigestModel.day),
        )
        return [Digest.model_validate(r) for r in result.scalars()]

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        day: int,
        phase: str,
        content_md: str,
        item_message_ids: list[uuid.UUID],
    ) -> Digest:
        stmt = (
            pg_insert(DigestModel)
            .values(
                user_id=user_id,
                project_id=project_id,
                day=day,
                phase=phase,
                content_md=content_md,
                item_message_ids=item_message_ids,
            )
            .on_conflict_do_update(
                index_elements=[DigestModel.user_id, DigestModel.day, DigestModel.phase],
                set_={
                    "content_md": content_md,
                    "item_message_ids": item_message_ids,
                    "project_id": project_id,
                },
            )
            .returning(DigestModel)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one()
        return Digest.model_validate(row)
