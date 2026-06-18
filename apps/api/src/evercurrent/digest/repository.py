"""SQL for digests: upsert a generated digest (idempotent per member + day) and
the read queries that gather a member's scored items, open signals, and history."""

from __future__ import annotations

import datetime as dt
import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Digest as DigestModel
from evercurrent.digest.schemas import (
    DigestMessageRow,
    DigestRecord,
    MemberProfile,
    PriorDigest,
    ProjectSnapshot,
    ScoredItem,
    SignalSummary,
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
                    "       content_md, signal_ids, message_ids, generated_at "
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
                    "       content_md, signal_ids, message_ids, generated_at "
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
    signal_ids: list[uuid.UUID],
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
            signal_ids=signal_ids,
            message_ids=message_ids,
        )
        .on_conflict_do_update(
            index_elements=["project_member_id", "day_index"],
            set_={
                "phase": phase,
                "content_md": content_md,
                "signal_ids": signal_ids,
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
                    # Drop chatter whose thread already has a resolved signal —
                    # resolution, not age, ages a message out. No time window:
                    # long unresolved threads must keep surfacing.
                    "  AND NOT EXISTS ( "
                    "    SELECT 1 FROM signals sig "
                    "    JOIN messages tm ON tm.id = sig.triggering_message_id "
                    "    WHERE sig.status = 'resolved' "
                    "      AND COALESCE(tm.thread_root_id, tm.id) "
                    "          = COALESCE(m.thread_root_id, m.id) "
                    "  ) "
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


async def open_signals_for_member_subsystems(
    session: AsyncSession,
    *,
    project_id: uuid.UUID | None,
    owned_subsystems: list[str],
    limit: int = 20,
) -> list[SignalSummary]:
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
                    f"FROM signals WHERE {where} "
                    "ORDER BY updated_at DESC LIMIT :lim",
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return [
        SignalSummary(
            signal_id=uuid.UUID(str(r["id"])),
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


async def load_member_profile(
    session: AsyncSession,
    project_member_id: uuid.UUID,
) -> tuple[MemberProfile, uuid.UUID] | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, org_id, display_name, role, eng_role, "
                    "owned_subsystems, topic_weights, timezone "
                    "FROM org_memberships WHERE id = :id",
                ),
                {"id": str(project_member_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    org_id = uuid.UUID(str(row["org_id"]))
    topic_weights: dict[str, float] = dict(row["topic_weights"] or {})
    subsystems: list[str] = list(row["owned_subsystems"] or [])
    eng_role = row["eng_role"] or row["role"]
    profile = MemberProfile(
        project_member_id=uuid.UUID(str(row["id"])),
        display_name=str(row["display_name"] or ""),
        role=str(eng_role or "member"),
        timezone=str(row["timezone"] or "UTC"),
        owned_subsystems=subsystems,
        topic_weights=topic_weights,
    )
    return profile, org_id


async def load_project_snapshot(
    session: AsyncSession,
    *,
    phase: str,
    project_id: uuid.UUID | None,
) -> ProjectSnapshot:
    if project_id is None:
        return ProjectSnapshot(
            project_id=uuid.UUID(int=0),
            name="(unknown)",
            current_phase=phase,
            phase_concerns=[],
        )
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, name, current_phase, phase_concerns FROM projects WHERE id = :id",
                ),
                {"id": str(project_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return ProjectSnapshot(
            project_id=project_id,
            name="(unknown)",
            current_phase=phase,
            phase_concerns=[],
        )
    concerns_raw = row["phase_concerns"] or {}
    concerns_list = list(concerns_raw.get(phase, [])) if isinstance(concerns_raw, dict) else []
    return ProjectSnapshot(
        project_id=uuid.UUID(str(row["id"])),
        name=str(row["name"] or "(unknown)"),
        current_phase=str(row["current_phase"] or phase),
        phase_concerns=[str(c) for c in concerns_list],
    )


async def latest_project_id_for_org(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
) -> uuid.UUID | None:
    row = (
        await session.execute(
            text(
                "SELECT id FROM projects WHERE org_id = :oid ORDER BY created_at DESC LIMIT 1",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if row is None:
        return None
    return uuid.UUID(str(row[0]))


async def count_resolved_cited_signals(
    session: AsyncSession,
    *,
    signal_ids: list[uuid.UUID],
) -> int:
    """How many of a digest's cited signals are no longer open — the digest's
    narrative talks about them as live, so any closure makes it stale."""
    if not signal_ids:
        return 0
    return int(
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM signals "
                    "WHERE id = ANY(:ids) AND status <> 'open'",
                ),
                {"ids": [str(i) for i in signal_ids]},
            )
        ).scalar_one(),
    )


async def count_new_scored_since(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    since: dt.datetime,
) -> int:
    """New scored messages for the member since the digest was generated — a
    cheap proxy for 'new activity worth a refresh'."""
    return int(
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM scores "
                    "WHERE project_member_id = :mid AND computed_at > :since",
                ),
                {"mid": str(project_member_id), "since": since},
            )
        ).scalar_one(),
    )


async def member_timezone(session: AsyncSession, project_member_id: uuid.UUID) -> str:
    row = (
        await session.execute(
            text("SELECT timezone FROM org_memberships WHERE id = :id"),
            {"id": str(project_member_id)},
        )
    ).first()
    return str(row[0]) if row and row[0] else "UTC"


async def project_start_date(session: AsyncSession, *, org_id: uuid.UUID) -> dt.date | None:
    row = (
        await session.execute(
            text(
                "SELECT start_date FROM projects WHERE org_id = :oid "
                "ORDER BY created_at DESC LIMIT 1",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if row is None or row[0] is None:
        return None
    return row[0]


async def project_current_phase(session: AsyncSession, *, org_id: uuid.UUID) -> str | None:
    row = (
        await session.execute(
            text(
                "SELECT current_phase FROM projects WHERE org_id = :oid "
                "ORDER BY created_at DESC LIMIT 1",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if row is None or row[0] is None:
        return None
    return str(row[0])
