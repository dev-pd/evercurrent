from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.agent_tools.schemas import CardRef

log = structlog.get_logger(__name__)

_SQL = text(
    """
    SELECT
        id,
        kind,
        summary,
        status,
        affected_subsystems,
        decided_at
    FROM cards
    WHERE (CAST(:kind AS text) IS NULL OR kind = :kind)
      AND (CAST(:status AS text) IS NULL OR status = :status)
    ORDER BY created_at DESC
    LIMIT :limit
    """,
).bindparams(
    bindparam("kind"),
    bindparam("status"),
    bindparam("limit"),
)


async def query_cards(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    kind: str | None = None,
    status: str | None = None,
    limit: int = 25,
) -> list[CardRef]:
    start = time.perf_counter()
    _ = project_id
    result = await session.execute(
        _SQL,
        {"kind": kind, "status": status, "limit": limit},
    )
    rows = list(result.mappings())

    out = [
        CardRef(
            id=r["id"],
            kind=r["kind"],
            summary=r["summary"],
            status=r["status"],
            affected_subsystems=list(r["affected_subsystems"] or []),
            decided_at=r["decided_at"],
        )
        for r in rows
    ]

    duration_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "mcp.tool_call",
        tool_name="query_cards",
        kind=kind,
        status=status,
        result_count=len(out),
        duration_ms=duration_ms,
    )
    return out
