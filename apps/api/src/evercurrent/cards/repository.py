"""Repository helpers for `cards` + `card_sources`.

All reads / writes go through these functions so the routes never see
raw SQL. RLS is set on the session by the caller (auth dep or task
body); these helpers do not set or clear it.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.cards.schemas import (
    CardKindT,
    CardListItem,
    CardResponse,
    CardSourceRef,
    CardStatusT,
    SourceKindT,
)


async def get_existing_card(
    session: AsyncSession,
    *,
    triggering_message_id: uuid.UUID,
    kind: str,
) -> dict[str, Any] | None:
    """Return the existing Card row for (message, kind), if any.

    Used by the builder for the idempotency check before calling Sonnet.
    """
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
    """Insert a Card row, returning its id."""
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
    """Bulk-insert source refs for a Card. Deduplicates within the call."""
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
    project_id: uuid.UUID,
    kind: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[CardListItem]:
    """List Cards for a project, ordered by updated_at desc."""
    clauses = ["project_id = :project_id"]
    params: dict[str, Any] = {"project_id": str(project_id), "limit": limit}
    if kind is not None:
        clauses.append("kind = :kind")
        params["kind"] = kind
    if status is not None:
        clauses.append("status = :status")
        params["status"] = status
    where = " AND ".join(clauses)
    result = await session.execute(
        text(
            f"SELECT c.id, c.kind, c.summary, c.status, c.confidence, "
            f"       c.decided_at, c.updated_at, "
            f"       (SELECT COUNT(*) FROM card_sources cs "
            f"        WHERE cs.card_id = c.id) AS sources_count "
            f"FROM cards c WHERE {where} "
            f"ORDER BY c.updated_at DESC LIMIT :limit",
        ),
        params,
    )
    rows = result.mappings().all()
    return [
        CardListItem(
            id=uuid.UUID(str(r["id"])),
            kind=_cast_kind(str(r["kind"])),
            summary=str(r["summary"]),
            status=_cast_status(str(r["status"])),
            confidence=float(r["confidence"]),
            decided_at=r["decided_at"],
            sources_count=int(r["sources_count"] or 0),
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


async def get_card(
    session: AsyncSession,
    card_id: uuid.UUID,
) -> CardResponse | None:
    """Get one Card with expanded source snippets."""
    result = await session.execute(
        text(
            "SELECT id, kind, summary, body, status, confidence, "
            "       decided_at, affected_subsystems, created_at, updated_at "
            "FROM cards WHERE id = :id",
        ),
        {"id": str(card_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None

    src_result = await session.execute(
        text(
            "SELECT source_kind, source_id FROM card_sources "
            "WHERE card_id = :id ORDER BY created_at ASC",
        ),
        {"id": str(card_id)},
    )
    sources: list[CardSourceRef] = []
    for s in src_result.mappings().all():
        kind = str(s["source_kind"])
        sid = uuid.UUID(str(s["source_id"]))
        snippet = await _resolve_source_snippet(session, kind, sid)
        sources.append(
            CardSourceRef(
                source_kind=_cast_source_kind(kind),
                source_id=sid,
                snippet=snippet,
            ),
        )

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


async def _resolve_source_snippet(
    session: AsyncSession,
    source_kind: str,
    source_id: uuid.UUID,
) -> str | None:
    """Best-effort snippet lookup for a source citation."""
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
                    "SELECT section_path, text FROM document_chunks "
                    "WHERE id = :id",
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
