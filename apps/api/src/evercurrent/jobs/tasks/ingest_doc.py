"""Arq task: chunk + embed + index a single document."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def ingest_document(_ctx: dict[str, Any], document_id: str) -> dict[str, Any]:
    from evercurrent.rag.indexer import index_document

    doc_uuid = uuid.UUID(document_id)
    chunks = await index_document(doc_uuid)
    log.info("rag.ingest.done", document_id=document_id, chunks=chunks)
    return {"document_id": document_id, "chunks": chunks}
