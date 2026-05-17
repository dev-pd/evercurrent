"""RAG indexer. Pipeline: doc → chunks → embeddings → pgvector."""

from __future__ import annotations

import uuid

import structlog

from evercurrent.db.repositories import DocumentRepository
from evercurrent.db.session import session_scope
from evercurrent.rag.chunker import chunk_markdown
from evercurrent.rag.embedder import EmbeddingProvider, get_embedder

log = structlog.get_logger(__name__)


async def index_document(
    document_id: uuid.UUID,
    *,
    embedder: EmbeddingProvider | None = None,
) -> int:
    """Chunk + embed + replace all chunks for one document. Idempotent."""
    emb = embedder or get_embedder()

    async with session_scope() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if document is None:
            log.warning("rag.index.missing_doc", document_id=str(document_id))
            return 0

        chunks = chunk_markdown(document.body)
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = await emb.embed_documents(texts)

        rows: list[dict[str, object]] = [
            {
                "chunk_index": c.chunk_index,
                "section_path": c.section_path,
                "text": c.text,
                "embedding": e,
                "metadata": {**c.metadata, "document_kind": document.kind.value},
            }
            for c, e in zip(chunks, embeddings, strict=True)
        ]
        count = await repo.replace_chunks(document.id, rows)
        await session.commit()

    log.info(
        "rag.index.document",
        document_id=str(document_id),
        title=document.title,
        chunks=count,
    )
    return count


async def index_all_for_project(project_id: uuid.UUID) -> dict[str, int]:
    """Index every document for a project. Returns {document_title: chunk_count}."""
    out: dict[str, int] = {}
    async with session_scope() as session:
        repo = DocumentRepository(session)
        documents = await repo.list_for_project(project_id)
    for d in documents:
        out[d.title] = await index_document(d.id)
    return out


def main() -> None:
    """CLI: `python -m evercurrent.rag.indexer --all` indexes every doc."""
    import argparse

    parser = argparse.ArgumentParser(description="Index project documents for RAG.")
    parser.add_argument("--all", action="store_true", help="Index every document")
    parser.add_argument("--project-name", default="Warehouse Robot v2")
    args = parser.parse_args()

    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from evercurrent.db.repositories import ProjectRepository

    async def _run() -> None:
        async with session_scope() as session:
            project = await ProjectRepository(session).get_by_name(args.project_name)
        if project is None:
            msg = f"project {args.project_name!r} not found; run `make seed` first."
            raise RuntimeError(msg)
        if args.all:
            result = await index_all_for_project(project.id)
            for title, count in result.items():
                log.info("rag.cli.indexed", title=title, chunks=count)
        else:
            log.info("rag.cli.usage", message="Pass --all to index every doc.")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
