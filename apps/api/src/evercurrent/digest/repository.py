"""Persistence + read helpers for the v2 `digests` table.

The agent calls `upsert_digest(...)` after Sonnet returns a parsed
`DigestDraft`. The routes call `get_latest_for_member(...)` and
`get_for_member_day(...)`. The scheduler calls `list_active_memberships(...)`.

All SQL stays here so the agent module is purely orchestration.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Digest as DigestModel
from evercurrent.digest.schemas import (
    CardSummary,
    PriorDigest,
    ScoredItem,
)
from evercurrent.domain.digests import Digest

log = structlog.get_logger(__name__)


async def get_for_member_day(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    day_index: int,
) -> Digest | None:
    """Return the digest row for (member, day_index) if it exists."""
    row = (
        await session.execute(
            text(
                "SELECT id, org_id, project_member_id, day_index, phase, "
                "       content_md, card_ids, message_ids, generated_at "
                "FROM digests "
                "WHERE project_member_id = :mid AND day_index = :d",
            ),
            {"mid": str(project_member_id), "d": day_index},
        )
    ).mappings().first()
    if row is None:
        return None
    return Digest.model_validate(dict(row))


async def get_latest_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
) -> Digest | None:
    """Return the most recent digest row for the member, by day_index DESC."""
    row = (
        await session.execute(
            text(
                "SELECT id, org_id, project_member_id, day_index, phase, "
                "       content_md, card_ids, message_ids, generated_at "
                "FROM digests "
                "WHERE project_member_id = :mid "
                "ORDER BY day_index DESC, generated_at DESC LIMIT 1",
            ),
            {"mid": str(project_member_id)},
        )
    ).mappings().first()
    if row is None:
        return None
    return Digest.model_validate(dict(row))


async def list_recent_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    before_day_index: int,
    limit: int = 3,
) -> list[PriorDigest]:
    """Return the most recent `limit` digests strictly before `before_day_index`."""
    rows = (
        await session.execute(
            text(
                "SELECT day_index, content_md FROM digests "
                "WHERE project_member_id = :mid AND day_index < :d "
                "ORDER BY day_index DESC LIMIT :lim",
            ),
            {
                "mid": str(project_member_id),
                "d": before_day_index,
                "lim": limit,
            },
        )
    ).mappings().all()
    return [
        PriorDigest(day_index=int(r["day_index"]), content_md=str(r["content_md"]))
        for r in rows
    ]


async def upsert_digest(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_member_id: uuid.UUID,
    day_index: int,
    phase: str,
    content_md: str,
    card_ids: list[uuid.UUID],
    message_ids: list[uuid.UUID],
) -> Digest:
    """Insert or overwrite the digest for (member, day_index)."""
    stmt = (
        pg_insert(DigestModel)
        .values(
            org_id=org_id,
            project_member_id=project_member_id,
            day_index=day_index,
            phase=phase,
            content_md=content_md,
            card_ids=card_ids,
            message_ids=message_ids,
        )
        .on_conflict_do_update(
            index_elements=["project_member_id", "day_index"],
            set_={
                "phase": phase,
                "content_md": content_md,
                "card_ids": card_ids,
                "message_ids": message_ids,
                "generated_at": text("now()"),
            },
        )
        .returning(DigestModel)
    )
    result = await session.execute(stmt)
    row = result.scalar_one()
    return Digest.model_validate(row)


async def top_scored_items_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    limit: int = 20,
) -> list[ScoredItem]:
    """Return the top-N scored messages for the member, score DESC."""
    rows = (
        await session.execute(
            text(
                "SELECT s.message_id, s.score, "
                "       mt.topic AS topic, mt.urgency AS urgency, "
                "       m.channel AS channel, m.author_display_name AS author, "
                "       m.text AS text, m.posted_at AS posted_at "
                "FROM scores s "
                "JOIN messages m ON m.id = s.message_id "
                "LEFT JOIN message_tags mt ON mt.message_id = m.id "
                "WHERE s.project_member_id = :mid "
                "ORDER BY s.score DESC, m.posted_at DESC LIMIT :lim",
            ),
            {"mid": str(project_member_id), "lim": limit},
        )
    ).mappings().all()
    return [
        ScoredItem(
            message_id=uuid.UUID(str(r["message_id"])),
            score=float(r["score"]),
            topic=str(r["topic"]) if r["topic"] is not None else None,
            urgency=str(r["urgency"]) if r["urgency"] is not None else None,
            channel=str(r["channel"]) if r["channel"] is not None else None,
            author=str(r["author"]) if r["author"] is not None else None,
            text=str(r["text"] or ""),
            posted_at=r["posted_at"],
        )
        for r in rows
    ]


async def open_cards_for_member_subsystems(
    session: AsyncSession,
    *,
    project_id: uuid.UUID | None,
    owned_subsystems: list[str],
    limit: int = 20,
) -> list[CardSummary]:
    """Return open Cards whose affected_subsystems intersect with member's owned set.

    Empty `owned_subsystems` returns `[]` — without an owned set we have
    no signal to filter cards by, and the digest is not a generic dump.
    """
    if not owned_subsystems:
        return []

    params: dict[str, object] = {
        "subsystems": owned_subsystems,
        "lim": limit,
    }
    where = "status = 'open' AND affected_subsystems && CAST(:subsystems AS text[])"
    if project_id is not None:
        where += " AND project_id = :pid"
        params["pid"] = str(project_id)

    rows = (
        await session.execute(
            text(
                "SELECT id, kind, summary, status, affected_subsystems, "
                "       updated_at "
                f"FROM cards WHERE {where} "
                "ORDER BY updated_at DESC LIMIT :lim",
            ),
            params,
        )
    ).mappings().all()
    return [
        CardSummary(
            card_id=uuid.UUID(str(r["id"])),
            kind=str(r["kind"]),
            summary=str(r["summary"]),
            status=str(r["status"]),
            affected_subsystems=list(r["affected_subsystems"] or []),
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


async def list_active_memberships(
    session: AsyncSession,
) -> list[dict[str, object]]:
    """Return rows of {id, org_id, timezone} for every org membership.

    The scheduler iterates this list every minute deciding which members
    are at 08:00 local and need a digest. Tight projection — no PII.
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, org_id, timezone FROM org_memberships",
            ),
        )
    ).mappings().all()
    return [dict(r) for r in rows]
