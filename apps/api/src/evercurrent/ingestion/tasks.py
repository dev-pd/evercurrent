"""Async impl behind the `ingest_document` Celery task.

Pipeline:

1. Extract blocks from the PDF (or fetch text via `files.export` for
   Google Docs).
2. Chunk via the paragraph-aware sliding window.
3. Embed in batches of 128 via Voyage.
4. Upsert a `documents` row keyed by `(source, external_id)` —
   idempotent. Replace chunks.
5. Run the Haiku classifier on title + first 3 chunks.
6. Publish `document_ingested` to Redis for SSE consumers.

Two entrypoints:

- `ingest_pdf_bytes(...)` — used by the mock-drive path (no Drive call)
- `ingest_drive_file(...)` — used by the live Drive webhook path
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select, text

from evercurrent.config import get_settings
from evercurrent.connectors.drive.client import DriveClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.db.session import session_scope
from evercurrent.ingestion.chunking import Chunk, chunk_blocks
from evercurrent.ingestion.classifier import classify_document
from evercurrent.ingestion.pdf_extract import Block, extract_blocks
from evercurrent.ingestion.schemas import DocClassification
from evercurrent.rag.embedder import EmbeddingProvider, get_embedder
from evercurrent.realtime import publish_event
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)

MAX_BYTES = 50 * 1024 * 1024
DECISION_CONFIDENCE_THRESHOLD = 0.7
PDF_MIME = "application/pdf"
GDOC_MIME = "application/vnd.google-apps.document"


async def _upsert_document(
    *,
    session: Any,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    source: str,
    external_id: str,
    kind: str,
    title: str,
) -> tuple[uuid.UUID, bool]:
    """Insert-or-fetch a documents row. Returns (id, created_new)."""
    existing = (
        await session.execute(
            select(models.Document).where(
                models.Document.source == source,
                models.Document.external_id == external_id,
            ),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing.id, False
    row = models.Document(
        org_id=org_id,
        project_id=project_id,
        source=source,
        external_id=external_id,
        kind=kind,
        title=title,
    )
    session.add(row)
    await session.flush()
    return row.id, True


async def _replace_chunks(
    *,
    session: Any,
    document_id: uuid.UUID,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> int:
    if len(chunks) != len(embeddings):
        msg = "chunks/embeddings length mismatch"
        raise ValueError(msg)
    existing_rows = (
        await session.execute(
            select(models.DocumentChunk).where(
                models.DocumentChunk.document_id == document_id,
            ),
        )
    ).scalars().all()
    for row in existing_rows:
        await session.delete(row)
    await session.flush()
    for c, emb in zip(chunks, embeddings, strict=True):
        session.add(
            models.DocumentChunk(
                document_id=document_id,
                chunk_index=c.ordinal,
                section_path=c.section,
                text=c.text,
                embedding=emb,
                metadata_={"page_start": c.page_start},
            ),
        )
    await session.flush()
    return len(chunks)


async def _resolve_default_project(
    *,
    session: Any,
    org_id: uuid.UUID,
) -> uuid.UUID | None:
    """For take-home scope, pick *any* project in the org as the doc's owner.

    Uses raw SQL because `models.Project.org_id` isn't declared on the
    Phase 1 ORM (the column exists in the migrated schema; we don't
    retrofit the ORM until Phase 9 finishes the data-model swap).
    """
    result = await session.execute(
        text("SELECT id FROM projects WHERE org_id = :org_id LIMIT 1"),
        {"org_id": str(org_id)},
    )
    row = result.first()
    if row is None:
        return None
    return uuid.UUID(str(row[0]))


async def _publish_ingested(
    *,
    project_id: uuid.UUID | None,
    document_id: uuid.UUID,
    title: str,
    classification: DocClassification | None,
) -> None:
    if project_id is None:
        return
    payload: dict[str, Any] = {
        "document_id": str(document_id),
        "title": title,
        "kind": classification.kind if classification else None,
        "is_decision": classification.is_decision if classification else False,
    }
    publish_event(project_id, "document_ingested", payload)


async def _ingest_blocks(
    *,
    blocks: list[Block],
    org_id: uuid.UUID,
    source: str,
    external_id: str,
    title: str,
    kind_hint: str,
    embedder: EmbeddingProvider | None,
) -> dict[str, Any]:
    """Shared core: chunk + embed + persist + classify + publish."""
    chunks = chunk_blocks(blocks)
    if not chunks:
        log.info(
            "ingest.empty",
            source=source,
            external_id=external_id,
            title=title,
        )
        return {"document_id": None, "chunks": 0, "skipped": "empty"}

    emb = embedder or get_embedder()
    texts = [c.text for c in chunks]
    embeddings = await emb.embed_documents(texts)

    async with session_scope() as session:
        await set_org_context(session, org_id)
        project_id = await _resolve_default_project(session=session, org_id=org_id)
        if project_id is None:
            log.warning("ingest.no_project_for_org", org_id=str(org_id))
            return {"document_id": None, "chunks": 0, "skipped": "no_project"}
        document_id, created_new = await _upsert_document(
            session=session,
            org_id=org_id,
            project_id=project_id,
            source=source,
            external_id=external_id,
            kind=kind_hint,
            title=title,
        )
        if not created_new:
            await session.commit()
            log.info(
                "ingest.idempotent_skip",
                document_id=str(document_id),
                external_id=external_id,
            )
            return {
                "document_id": str(document_id),
                "chunks": 0,
                "skipped": "duplicate",
            }
        chunk_count = await _replace_chunks(
            session=session,
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        await session.commit()

    classification: DocClassification | None = None
    try:
        classification = await classify_document(title=title, chunks=chunks)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "ingest.classify_failed",
            document_id=str(document_id),
            error=str(exc),
        )

    await _publish_ingested(
        project_id=project_id,
        document_id=document_id,
        title=title,
        classification=classification,
    )

    return {
        "document_id": str(document_id),
        "chunks": chunk_count,
        "classification": classification.model_dump() if classification else None,
    }


async def ingest_pdf_bytes(
    *,
    org_id: uuid.UUID,
    source: str,
    external_id: str,
    title: str,
    pdf_bytes: bytes,
    kind_hint: str = "pdf",
    embedder: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    """Ingest a PDF given its raw bytes. Used by mock-drive + Drive paths."""
    if len(pdf_bytes) > MAX_BYTES:
        log.warning(
            "ingest.too_large",
            external_id=external_id,
            size=len(pdf_bytes),
        )
        return {"document_id": None, "chunks": 0, "skipped": "too_large"}
    blocks = extract_blocks(pdf_bytes)
    return await _ingest_blocks(
        blocks=blocks,
        org_id=org_id,
        source=source,
        external_id=external_id,
        title=title,
        kind_hint=kind_hint,
        embedder=embedder,
    )


async def ingest_pdf_path(
    *,
    org_id: uuid.UUID,
    source: str,
    external_id: str,
    title: str,
    pdf_path: Path,
    kind_hint: str = "pdf",
    embedder: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    blocks = extract_blocks(pdf_path)
    return await _ingest_blocks(
        blocks=blocks,
        org_id=org_id,
        source=source,
        external_id=external_id,
        title=title,
        kind_hint=kind_hint,
        embedder=embedder,
    )


async def ingest_drive_file(
    *,
    connector_id: uuid.UUID,
    drive_file_id: str,
    embedder: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    """Live-Drive path: download, dispatch by mime type, run the pipeline."""
    settings = get_settings()
    if settings.connector_secret_key is None:
        log.error("ingest.drive.no_secret_key")
        return {"document_id": None, "chunks": 0, "skipped": "no_secret_key"}
    vault = TokenVault(settings.connector_secret_key)

    async with session_scope() as session:
        connector = await session.get(models.Connector, connector_id)
        if connector is None:
            log.warning("ingest.drive.missing_connector", connector_id=str(connector_id))
            return {"document_id": None, "chunks": 0, "skipped": "missing_connector"}
        org_id = connector.org_id
        blob = vault.decrypt(connector.credentials_secret)
        token_payload = json.loads(blob)
        access_token = str(token_payload["access_token"])

    client = DriveClient(access_token=access_token)
    try:
        meta = await client.files_get_metadata(drive_file_id)
        if _is_google_doc(meta.mime_type):
            exported = await client.files_export_text(drive_file_id)
            # For text-exported Docs, use a synthetic single-block layout.
            blocks = [Block(page=1, bbox=(0.0, 0.0, 0.0, 0.0), text=exported)]
            return await _ingest_blocks(
                blocks=blocks,
                org_id=org_id,
                source="drive",
                external_id=drive_file_id,
                title=meta.name,
                kind_hint="gdoc",
                embedder=embedder,
            )
        if not _is_pdf(meta.mime_type):
            log.info(
                "ingest.drive.skipped_mime",
                file_id=drive_file_id,
                mime_type=meta.mime_type,
            )
            return {
                "document_id": None,
                "chunks": 0,
                "skipped": f"mime:{meta.mime_type}",
            }
        pdf_bytes = await client.files_download_bytes(drive_file_id)
    finally:
        await client.aclose()

    return await ingest_pdf_bytes(
        org_id=org_id,
        source="drive",
        external_id=drive_file_id,
        title=meta.name,
        pdf_bytes=pdf_bytes,
        kind_hint="pdf",
        embedder=embedder,
    )


def _is_pdf(mime_type: str) -> bool:
    return mime_type == PDF_MIME


def _is_google_doc(mime_type: str) -> bool:
    return mime_type == GDOC_MIME
