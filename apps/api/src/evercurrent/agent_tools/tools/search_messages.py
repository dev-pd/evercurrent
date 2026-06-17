from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.agent_tools.schemas import MessageRef

log = structlog.get_logger(__name__)

_SQL = text(
    """
    SELECT
        m.id AS id,
        COALESCE(m.channel, '') AS channel,
        m.author_display_name AS author,
        m.text AS text,
        m.posted_at AS posted_at
    FROM messages m
    WHERE m.text ILIKE ANY(:patterns)
    ORDER BY m.posted_at DESC
    LIMIT :limit
    """,
).bindparams(
    bindparam("patterns"),
    bindparam("limit"),
)

_MIN_TOKEN_LEN = 3
_STOPWORDS = frozenset(
    {"the", "and", "for", "with", "from", "that", "this", "what", "any", "are"},
)


async def search_messages(
    session: AsyncSession,
    *,
    query: str,
    project_id: uuid.UUID,
    limit: int = 10,
) -> list[MessageRef]:
    start = time.perf_counter()
    cleaned = query.strip()
    if not cleaned:
        log.info(
            "mcp.tool_call",
            tool_name="search_messages",
            project_id=str(project_id),
            query_len=0,
            result_count=0,
            duration_ms=0,
        )
        return []

    _ = project_id
    tokens = [
        w for w in cleaned.lower().split() if len(w) >= _MIN_TOKEN_LEN and w not in _STOPWORDS
    ]
    patterns = [f"%{cleaned}%", *(f"%{w}%" for w in tokens[:8])]
    result = await session.execute(
        _SQL,
        {"patterns": patterns, "limit": limit},
    )
    rows = list(result.mappings())

    out = [
        MessageRef(
            id=r["id"],
            channel=r["channel"],
            author=r["author"],
            text=r["text"],
            posted_at=r["posted_at"],
            score=None,
        )
        for r in rows
    ]

    duration_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "mcp.tool_call",
        tool_name="search_messages",
        project_id=str(project_id),
        query_len=len(cleaned),
        result_count=len(out),
        duration_ms=duration_ms,
    )
    return out
