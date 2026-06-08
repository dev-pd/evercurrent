"""query_cards tool.

SQL filter over the `cards` table. The `cards` table doesn't exist yet
(Phase 6); for now this queries the `decisions` table and maps it onto
the `CardRef` shape so agents written in Phase 5 can consume a stable
contract. When the `cards` table lands, this tool flips its SELECT
target without touching the response schema or any agent code.
"""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.mcp.schemas import CardRef

log = structlog.get_logger(__name__)

# TODO(phase-6): switch to cards table. For now we read `decisions` and
# treat `kind` as a fixed string "decision" since the decisions table has
# no per-row kind column.
_SQL = text(
    """
    SELECT
        d.id AS id,
        'decision' AS kind,
        d.summary AS summary,
        d.status AS status,
        d.decided_at AS decided_at
    FROM decisions d
    WHERE d.project_id = :project_id
      AND (:kind IS NULL OR :kind = 'decision')
      AND (:status IS NULL OR d.status = :status)
    ORDER BY d.decided_at DESC
    LIMIT :limit
    """,
).bindparams(
    bindparam("project_id"),
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
    """Return cards (placeholder: decisions) matching the kind + status filters."""
    start = time.perf_counter()
    result = await session.execute(
        _SQL,
        {
            "project_id": project_id,
            "kind": kind,
            "status": status,
            "limit": limit,
        },
    )
    rows = list(result.mappings())

    out = [
        CardRef(
            id=r["id"],
            kind=r["kind"],
            summary=r["summary"],
            status=r["status"],
            decided_at=r["decided_at"],
        )
        for r in rows
    ]

    duration_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "mcp.tool_call",
        tool_name="query_cards",
        project_id=str(project_id),
        kind=kind,
        status=status,
        result_count=len(out),
        duration_ms=duration_ms,
    )
    return out
