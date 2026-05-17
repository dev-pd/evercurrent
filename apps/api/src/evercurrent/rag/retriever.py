"""RAG retriever. pgvector cosine search with optional kind filter."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import bindparam, text

from evercurrent.db.session import session_scope
from evercurrent.rag.embedder import EmbeddingProvider, get_embedder

log = structlog.get_logger(__name__)

_LOW_CONFIDENCE_THRESHOLD = 0.4


@dataclass(frozen=True, slots=True)
class ChunkResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    document_kind: str
    section_path: str | None
    text: str
    similarity: float


async def search_documents(
    *,
    query: str,
    project_id: uuid.UUID,
    document_kinds: list[str] | None = None,
    top_k: int = 5,
    embedder: EmbeddingProvider | None = None,
) -> list[ChunkResult]:
    emb = embedder or get_embedder()
    query_vec = await emb.embed_query(query)

    sql = text(
        """
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS document_id,
            d.title AS document_title,
            d.kind AS document_kind,
            dc.section_path AS section_path,
            dc.text AS chunk_text,
            1 - (dc.embedding <=> CAST(:qvec AS vector)) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.project_id = :project_id
          AND (:kinds IS NULL OR d.kind = ANY(CAST(:kinds AS text[])))
          AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> CAST(:qvec AS vector)
        LIMIT :limit
        """,
    ).bindparams(
        bindparam("qvec"),
        bindparam("project_id"),
        bindparam("kinds"),
        bindparam("limit"),
    )

    qvec_literal = "[" + ",".join(f"{v:.7f}" for v in query_vec) + "]"

    async with session_scope() as session:
        result = await session.execute(
            sql,
            {
                "qvec": qvec_literal,
                "project_id": project_id,
                "kinds": document_kinds,
                "limit": top_k,
            },
        )
        rows = list(result.mappings())

    out = [
        ChunkResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            document_title=r["document_title"],
            document_kind=r["document_kind"],
            section_path=r["section_path"],
            text=r["chunk_text"],
            similarity=float(r["similarity"]),
        )
        for r in rows
    ]

    if out and out[0].similarity < _LOW_CONFIDENCE_THRESHOLD:
        log.warning(
            "rag.search.low_confidence",
            query=query,
            top_similarity=out[0].similarity,
        )
    return out
