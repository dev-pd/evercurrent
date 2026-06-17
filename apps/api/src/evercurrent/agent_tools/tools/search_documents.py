"""Tool: semantic search over spec/BOM/requirement document chunks (the formal
source of truth) via pgvector."""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.agent_tools.schemas import ChunkRef
from evercurrent.rag.embedder import EmbeddingProvider, get_embedder

log = structlog.get_logger(__name__)

_SQL = text(
    """
    SELECT
        dc.document_id AS document_id,
        dc.chunk_index AS ordinal,
        dc.section_path AS section,
        dc.text AS text,
        1 - (dc.embedding <=> CAST(:qvec AS vector)) AS similarity
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE d.project_id = :project_id
      AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> CAST(:qvec AS vector)
    LIMIT :limit
    """,
).bindparams(
    bindparam("qvec"),
    bindparam("project_id"),
    bindparam("limit"),
)


async def search_documents(
    session: AsyncSession,
    *,
    query: str,
    project_id: uuid.UUID,
    limit: int = 5,
    embedder: EmbeddingProvider | None = None,
) -> list[ChunkRef]:
    start = time.perf_counter()
    cleaned = query.strip()
    if not cleaned:
        log.info(
            "tool.call",
            tool_name="search_documents",
            project_id=str(project_id),
            query_len=0,
            result_count=0,
            duration_ms=0,
        )
        return []

    emb = embedder or get_embedder()
    query_vec = await emb.embed_query(cleaned)
    qvec_literal = "[" + ",".join(f"{v:.7f}" for v in query_vec) + "]"

    result = await session.execute(
        _SQL,
        {"qvec": qvec_literal, "project_id": project_id, "limit": limit},
    )
    rows = list(result.mappings())

    out = [
        ChunkRef(
            document_id=r["document_id"],
            ordinal=int(r["ordinal"]),
            section=r["section"],
            text=r["text"],
            similarity=float(r["similarity"]),
        )
        for r in rows
    ]

    duration_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "tool.call",
        tool_name="search_documents",
        project_id=str(project_id),
        query_len=len(cleaned),
        result_count=len(out),
        duration_ms=duration_ms,
    )
    return out
