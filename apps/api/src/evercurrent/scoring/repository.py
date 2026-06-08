"""Persistence layer for `scores` rows.

The engine is pure; this module is the only place in `scoring/` that
talks to the DB. Idempotent upsert keyed on `(project_member_id,
message_id)` — the router can re-fire the scoring task without creating
duplicates.
"""

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
    """Insert or update one (member, message) score row."""
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
    """Insert many score rows in a single statement.

    Each row dict must carry `org_id`, `project_member_id`, `message_id`,
    `score`, and `reasons` keys.
    """
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
