"""Persistence for computed scores: idempotent upserts keyed on
(project_member_id, message_id) so re-scoring a message overwrites in place."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Score
from evercurrent.scoring.schemas import ScoreResult


async def upsert_score(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_member_id: uuid.UUID,
    message_id: uuid.UUID,
    result: ScoreResult,
) -> None:
    stmt = (
        insert(Score)
        .values(
            org_id=org_id,
            project_member_id=project_member_id,
            message_id=message_id,
            score=result.total,
            reasons=result.breakdown,
        )
        .on_conflict_do_update(
            index_elements=["project_member_id", "message_id"],
            set_={
                "score": result.total,
                "reasons": result.breakdown,
                "computed_at": insert(Score).excluded.computed_at,
            },
        )
    )
    await session.execute(stmt)


async def bulk_upsert_scores(
    session: AsyncSession,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        return
    stmt = (
        insert(Score)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["project_member_id", "message_id"],
            set_={
                "score": insert(Score).excluded.score,
                "reasons": insert(Score).excluded.reasons,
            },
        )
    )
    await session.execute(stmt)
