"""RAG eval — 30 question/expected-document pairs via pgvector ANN.

Setup:
1. Spin up Postgres with pgvector (testcontainers).
2. Create a minimal `documents` + `document_chunks` schema scoped to
   this eval — we deliberately do NOT bootstrap the full RLS / orgs /
   projects stack because this eval is measuring retrieval quality,
   not multi-tenancy.
3. Chunk each markdown doc in `data/rag_corpus/` and embed via Voyage.
4. For each question, embed via Voyage, run cosine ANN, compute
   precision@5 + MRR against the expected documents.

Skipped without `ANTHROPIC_API_KEY`-free `VOYAGE_API_KEY` — we still
need Voyage to embed. The Postgres container starts regardless.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from evercurrent.rag.chunker import chunk_markdown
from evercurrent.rag.embedder import EmbeddingProvider, VoyageEmbedder
from tests.evals.conftest import emit_metric_table, write_report
from tests.evals.runner import (
    mean_reciprocal_rank,
    precision_at_k,
    warn_if_below_baseline,
)

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS eval_documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_document_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES eval_documents(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    section_path  TEXT,
    text          TEXT NOT NULL,
    embedding     vector(512) NOT NULL,
    UNIQUE (document_id, chunk_index)
);
"""

_SEARCH_SQL = """
SELECT
    d.slug AS slug,
    c.chunk_index AS chunk_index,
    c.text AS text,
    1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
FROM eval_document_chunks c
JOIN eval_documents d ON d.id = c.document_id
ORDER BY c.embedding <=> CAST(:qvec AS vector)
LIMIT :k
"""


@pytest.fixture(scope="session")
def rag_postgres_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg17", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def rag_engine(rag_postgres_url: str) -> Iterator[AsyncEngine]:
    eng = create_async_engine(rag_postgres_url, echo=False, future=True)

    async def _setup() -> None:
        async with eng.begin() as conn:
            for stmt in _SCHEMA_SQL.split(";"):
                if stmt.strip():
                    await conn.execute(text(stmt))

    asyncio.run(_setup())
    try:
        yield eng
    finally:
        asyncio.run(eng.dispose())


async def _ingest_corpus(
    engine: AsyncEngine,
    corpus_dir: Path,
    embedder: EmbeddingProvider,
) -> dict[str, str]:
    """Chunk + embed + insert every doc in `corpus_dir`. Returns {slug: doc_id}."""
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    slug_to_id: dict[str, str] = {}

    docs = sorted(corpus_dir.glob("*.md"))  # noqa: ASYNC240  pytest+asyncio.run, not trio
    for path in docs:
        slug = path.stem  # e.g. "01_eco_178"
        body = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(body)
        if not chunks:
            continue
        texts = [c.text for c in chunks]
        embeddings = await embedder.embed_documents(texts)

        async with sessionmaker() as session:
            doc_id = uuid.uuid4()
            await session.execute(
                text(
                    "INSERT INTO eval_documents (id, slug, title, body) "
                    "VALUES (:id, :slug, :title, :body)",
                ),
                {"id": str(doc_id), "slug": slug, "title": slug, "body": body},
            )
            for c, emb in zip(chunks, embeddings, strict=True):
                qvec = "[" + ",".join(f"{v:.7f}" for v in emb) + "]"
                await session.execute(
                    text(
                        "INSERT INTO eval_document_chunks "
                        "(document_id, chunk_index, section_path, text, embedding) "
                        "VALUES (:doc, :idx, :sec, :txt, CAST(:emb AS vector))",
                    ),
                    {
                        "doc": str(doc_id),
                        "idx": c.chunk_index,
                        "sec": c.section_path,
                        "txt": c.text,
                        "emb": qvec,
                    },
                )
            await session.commit()
            slug_to_id[slug] = str(doc_id)

    return slug_to_id


async def _query(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    question: str,
    k: int,
) -> list[str]:
    """Return the slugs of the top-k chunks, in order."""
    qvec_list = await embedder.embed_query(question)
    qvec = "[" + ",".join(f"{v:.7f}" for v in qvec_list) + "]"
    result = await session.execute(
        text(_SEARCH_SQL),
        {"qvec": qvec, "k": k},
    )
    return [str(row.slug) for row in result.mappings()]


def test_rag_precision_and_mrr(
    rag_questions: list[dict[str, Any]],
    rag_corpus_dir: Path,
    rag_engine: AsyncEngine,
    voyage_available: bool,
) -> None:
    """End-to-end retrieval quality on hand-labelled question/source pairs."""
    if not voyage_available:
        pytest.skip("VOYAGE_API_KEY not set; RAG eval skipped.")

    embedder = VoyageEmbedder()

    async def _run() -> tuple[list[float], list[float], list[tuple[str, ...]]]:
        await _ingest_corpus(rag_engine, rag_corpus_dir, embedder)
        sessionmaker = async_sessionmaker(rag_engine, expire_on_commit=False)
        precisions: list[float] = []
        mrrs: list[float] = []
        rows: list[tuple[str, ...]] = [
            ("id", "p@5", "mrr", "top1_slug"),
        ]
        for q in rag_questions:
            async with sessionmaker() as session:
                retrieved = await _query(session, embedder, q["question"], k=5)
            # dedupe by slug, preserving order — multiple chunks per doc
            seen: set[str] = set()
            uniq_retrieved: list[str] = []
            for r in retrieved:
                if r not in seen:
                    seen.add(r)
                    uniq_retrieved.append(r)
            p = precision_at_k(uniq_retrieved, q["expected_docs"], k=5)
            m = mean_reciprocal_rank(uniq_retrieved, q["expected_docs"])
            precisions.append(p)
            mrrs.append(m)
            rows.append(
                (
                    q["id"],
                    f"{p:.2f}",
                    f"{m:.2f}",
                    uniq_retrieved[0] if uniq_retrieved else "(none)",
                ),
            )
        return precisions, mrrs, rows

    precisions, mrrs, rows = asyncio.run(_run())
    mean_p = sum(precisions) / len(precisions) if precisions else 0.0
    mean_m = sum(mrrs) / len(mrrs) if mrrs else 0.0
    rows.append(("--- summary ---", f"{mean_p:.3f}", f"{mean_m:.3f}", ""))
    emit_metric_table("rag eval (30 questions)", rows)

    warn_if_below_baseline("rag_precision_at_5", mean_p)
    warn_if_below_baseline("rag_mrr", mean_m)

    write_report(
        "rag",
        {
            "n_questions": len(rag_questions),
            "metrics": {
                "precision_at_5": mean_p,
                "mrr": mean_m,
            },
        },
    )
