"""SQL for cards: idempotent insert (one card per triggering message + kind),
source linking, and the paginated/detail read queries."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.cards.schemas import (
    CardKindT,
    CardListItem,
    CardPage,
    CardResponse,
    CardSourceDetail,
    CardStatusT,
    SourceKindT,
)
from evercurrent.connectors.slack.links import slack_permalink


async def get_existing_card(
    session: AsyncSession,
    *,
    triggering_message_id: uuid.UUID,
    kind: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            "SELECT id, org_id, project_id, kind, summary, body, status, "
            "       confidence, decided_at, affected_subsystems, "
            "       created_at, updated_at "
            "FROM cards "
            "WHERE triggering_message_id = :mid AND kind = :kind",
        ),
        {"mid": str(triggering_message_id), "kind": kind},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return dict(row)


async def insert_card(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None,
    kind: str,
    summary: str,
    body: str,
    affected_subsystems: list[str],
    confidence: float,
    decided_at: Any | None,
    triggering_message_id: uuid.UUID,
) -> uuid.UUID:
    result = await session.execute(
        text(
            "INSERT INTO cards "
            "(org_id, project_id, kind, summary, body, "
            " affected_subsystems, confidence, decided_at, "
            " triggering_message_id) "
            "VALUES (:org_id, :project_id, :kind, :summary, :body, "
            "        CAST(:subsystems AS text[]), :confidence, :decided_at, "
            "        :mid) "
            "RETURNING id",
        ),
        {
            "org_id": str(org_id),
            "project_id": str(project_id) if project_id else None,
            "kind": kind,
            "summary": summary,
            "body": body,
            "subsystems": affected_subsystems,
            "confidence": confidence,
            "decided_at": decided_at,
            "mid": str(triggering_message_id),
        },
    )
    row = result.first()
    if row is None:
        msg = "INSERT INTO cards did not return an id"
        raise RuntimeError(msg)
    return uuid.UUID(str(row[0]))


async def add_card_sources(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    card_id: uuid.UUID,
    refs: list[tuple[str, uuid.UUID]],
) -> None:
    seen: set[tuple[str, uuid.UUID]] = set()
    for kind, sid in refs:
        if (kind, sid) in seen:
            continue
        seen.add((kind, sid))
        await session.execute(
            text(
                "INSERT INTO card_sources "
                "(org_id, card_id, source_kind, source_id) "
                "VALUES (:org_id, :card_id, :kind, :sid) "
                "ON CONFLICT (card_id, source_kind, source_id) DO NOTHING",
            ),
            {
                "org_id": str(org_id),
                "card_id": str(card_id),
                "kind": kind,
                "sid": str(sid),
            },
        )


async def list_cards(
    session: AsyncSession,
    *,
    project_id: uuid.UUID | None = None,
    kind: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> CardPage:
    clauses = ["TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if project_id is not None:
        clauses.append("project_id = :project_id")
        params["project_id"] = str(project_id)
    if kind is not None:
        clauses.append("kind = :kind")
        params["kind"] = kind
    if status is not None:
        clauses.append("status = :status")
        params["status"] = status
    where = " AND ".join(clauses)

    total = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM cards c WHERE {where}"),
            params,
        )
    ).scalar_one()

    result = await session.execute(
        text(
            f"SELECT c.id, c.kind, c.summary, c.status, c.confidence, "
            f"       c.decided_at, c.updated_at, c.affected_subsystems, "
            f"       (SELECT m.posted_at FROM messages m "
            f"        WHERE m.id = c.triggering_message_id) AS occurred_at, "
            f"       (SELECT COUNT(*) FROM card_sources cs "
            f"        WHERE cs.card_id = c.id) AS sources_count "
            f"FROM cards c WHERE {where} "
            f"ORDER BY c.updated_at DESC LIMIT :limit OFFSET :offset",
        ),
        params,
    )
    rows = result.mappings().all()
    items = [
        CardListItem(
            id=uuid.UUID(str(r["id"])),
            kind=_cast_kind(str(r["kind"])),
            summary=str(r["summary"]),
            status=_cast_status(str(r["status"])),
            confidence=float(r["confidence"]),
            decided_at=r["decided_at"],
            occurred_at=r["occurred_at"],
            sources_count=int(r["sources_count"] or 0),
            affected_subsystems=list(r["affected_subsystems"] or []),
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return CardPage(items=items, total=int(total), limit=limit, offset=offset)


async def get_card(
    session: AsyncSession,
    card_id: uuid.UUID,
) -> CardResponse | None:
    result = await session.execute(
        text(
            "SELECT id, org_id, kind, summary, body, status, confidence, "
            "       decided_at, affected_subsystems, created_at, updated_at "
            "FROM cards WHERE id = :id",
        ),
        {"id": str(card_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None

    team_id = (
        await session.execute(
            text(
                "SELECT external_team_id FROM connectors "
                "WHERE org_id = :o AND kind = 'slack' LIMIT 1",
            ),
            {"o": str(row["org_id"])},
        )
    ).scalar_one_or_none()

    src_result = await session.execute(
        text(
            "SELECT source_kind, source_id FROM card_sources "
            "WHERE card_id = :id ORDER BY created_at ASC",
        ),
        {"id": str(card_id)},
    )
    sources: list[CardSourceDetail] = []
    for s in src_result.mappings().all():
        kind = str(s["source_kind"])
        sid = uuid.UUID(str(s["source_id"]))
        sources.append(await _resolve_source_detail(session, kind, sid, team_id))

    return CardResponse(
        id=uuid.UUID(str(row["id"])),
        kind=_cast_kind(str(row["kind"])),
        summary=str(row["summary"]),
        body=str(row["body"]),
        status=_cast_status(str(row["status"])),
        confidence=float(row["confidence"]),
        decided_at=row["decided_at"],
        affected_subsystems=list(row["affected_subsystems"] or []),
        sources=sources,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _resolve_source_detail(
    session: AsyncSession,
    source_kind: str,
    source_id: uuid.UUID,
    team_id: str | None,
) -> CardSourceDetail:
    if source_kind == "message":
        r = (
            (
                await session.execute(
                    text(
                        "SELECT m.channel, m.text, m.author_display_name, m.external_id, "
                        "       m.posted_at, cc.name AS channel_name "
                        "FROM messages m "
                        "LEFT JOIN connector_channels cc ON cc.external_id = m.channel "
                        "WHERE m.id = :id",
                    ),
                    {"id": str(source_id)},
                )
            )
            .mappings()
            .first()
        )
        if r is not None:
            channel_id = r["channel"]
            slack_ts = str(r["external_id"]) if r["external_id"] else None
            display_channel = r["channel_name"] or channel_id
            display_ts = r["posted_at"].isoformat() if r["posted_at"] else slack_ts
            return CardSourceDetail(
                id=source_id,
                kind="message",
                channel=display_channel,
                author_display_name=r["author_display_name"],
                ts=display_ts,
                text=str(r["text"] or ""),
                url=slack_permalink(team_id, channel_id, slack_ts),
            )
    snippet = await _resolve_source_snippet(session, source_kind, source_id)
    return CardSourceDetail(
        id=source_id,
        kind=_cast_source_kind(source_kind),
        text=snippet or "",
    )


async def _resolve_source_snippet(
    session: AsyncSession,
    source_kind: str,
    source_id: uuid.UUID,
) -> str | None:
    if source_kind == "message":
        r = (
            await session.execute(
                text("SELECT text FROM messages WHERE id = :id"),
                {"id": str(source_id)},
            )
        ).first()
        if r is None:
            return None
        body = str(r[0] or "")
        return body[:200]
    if source_kind == "document_chunk":
        r = (
            await session.execute(
                text(
                    "SELECT section_path, text FROM document_chunks WHERE id = :id",
                ),
                {"id": str(source_id)},
            )
        ).first()
        if r is None:
            return None
        section = str(r[0] or "") if r[0] is not None else ""
        body = str(r[1] or "")
        return f"{section}: {body[:200]}" if section else body[:200]
    return None


def _cast_kind(value: str) -> CardKindT:
    if value not in ("decision", "risk", "question"):
        msg = f"unexpected card kind: {value!r}"
        raise ValueError(msg)
    return cast("CardKindT", value)


def _cast_status(value: str) -> CardStatusT:
    if value not in ("open", "resolved", "dismissed"):
        msg = f"unexpected card status: {value!r}"
        raise ValueError(msg)
    return cast("CardStatusT", value)


def _cast_source_kind(value: str) -> SourceKindT:
    if value not in ("message", "document_chunk", "pr"):
        msg = f"unexpected source kind: {value!r}"
        raise ValueError(msg)
    return cast("SourceKindT", value)


async def project_phase_and_subsystems(
    session: AsyncSession,
    project_id: uuid.UUID | None,
) -> tuple[str, list[str]]:
    """The project's current phase + its known subsystems (from phase_concerns),
    used to ground the card draft prompt."""
    if project_id is None:
        return "unknown", []
    row = (
        await session.execute(
            text("SELECT current_phase, phase_concerns FROM projects WHERE id = :id"),
            {"id": str(project_id)},
        )
    ).first()
    if row is None:
        return "unknown", []
    phase = str(row[0] or "unknown")
    concerns = row[1] or {}
    subsystems = list(concerns.get("subsystems") or []) if isinstance(concerns, dict) else []
    return phase, [str(s) for s in subsystems]
