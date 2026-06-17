"""SQL for digests: upsert a generated digest (idempotent per member + day) and
the read queries that gather a member's scored items, open cards, and history."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Digest as DigestModel
from evercurrent.digest.schemas import (
    CardSummary,
    DigestMessageRow,
    DigestRecord,
    PriorDigest,
    ScoredItem,
)

log = structlog.get_logger(__name__)


async def get_for_member_day(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    day_index: int,
) -> DigestRecord | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, org_id, project_member_id, day_index, phase, "
                    "       content_md, card_ids, message_ids, generated_at "
                    "FROM digests "
                    "WHERE project_member_id = :mid AND day_index = :d",
                ),
                {"mid": str(project_member_id), "d": day_index},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return DigestRecord.model_validate(dict(row))


async def get_latest_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
) -> DigestRecord | None:
    row = (
        (
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
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return DigestRecord.model_validate(dict(row))


async def list_recent_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    before_day_index: int,
    limit: int = 3,
) -> list[PriorDigest]:
    rows = (
        (
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
        )
        .mappings()
        .all()
    )
    return [
        PriorDigest(day_index=int(r["day_index"]), content_md=str(r["content_md"])) for r in rows
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
) -> DigestRecord:
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
    return DigestRecord.model_validate(row)


async def top_scored_items_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    limit: int = 20,
) -> list[ScoredItem]:
    rows = (
        (
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
        )
        .mappings()
        .all()
    )
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
        (
            await session.execute(
                text(
                    "SELECT id, kind, summary, status, affected_subsystems, "
                    "       updated_at "
                    f"FROM cards WHERE {where} "
                    "ORDER BY updated_at DESC LIMIT :lim",
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
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
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id, org_id, timezone FROM org_memberships",
                ),
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


async def load_message_items(
    session: AsyncSession,
    *,
    message_ids: list[uuid.UUID],
) -> list[DigestMessageRow]:
    if not message_ids:
        return []
    rows = (
        (
            await session.execute(
                text(
                    "SELECT m.id, m.channel, m.author_display_name, "
                    "       m.posted_at, m.text, mt.urgency "
                    "FROM messages m "
                    "LEFT JOIN message_tags mt ON mt.message_id = m.id "
                    "WHERE m.id = ANY(:ids) "
                    "ORDER BY m.posted_at DESC",
                ),
                {"ids": [str(i) for i in message_ids]},
            )
        )
        .mappings()
        .all()
    )
    return [
        DigestMessageRow(
            id=r["id"],
            channel=r["channel"],
            author_display_name=r["author_display_name"],
            posted_at=r["posted_at"],
            text=r["text"],
            urgency=r["urgency"],
        )
        for r in rows
    ]
