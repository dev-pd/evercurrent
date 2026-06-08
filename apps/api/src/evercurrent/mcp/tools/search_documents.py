"""search_documents tool.

pgvector cosine ANN over `document_chunks`, scoped to a project. The
heavy lifting (query embedding + SQL) lives in `rag/retriever.py`; this
tool adapts that result to `ChunkRef` and wires it through the
caller-supplied AsyncSession so RLS context is preserved.
"""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.mcp.schemas import ChunkRef
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
    """Return up to `limit` chunks closest to `query` (cosine), scoped to project."""
    start = time.perf_counter()
    cleaned = query.strip()
    if not cleaned:
        log.info(
            "mcp.tool_call",
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
        "mcp.tool_call",
        tool_name="search_documents",
        project_id=str(project_id),
        query_len=len(cleaned),
        result_count=len(out),
        duration_ms=duration_ms,
    )
    return out
