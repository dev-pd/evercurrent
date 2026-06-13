from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Document as DocumentModel
from evercurrent.db.models import DocumentChunk as DocumentChunkModel
from evercurrent.domain.documents import Document, DocumentChunk, DocumentKind


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        row = await self._s.get(DocumentModel, document_id)
        return Document.model_validate(row) if row else None

    async def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        kinds: list[DocumentKind] | None = None,
    ) -> list[Document]:
        stmt = select(DocumentModel).where(DocumentModel.project_id == project_id)
        if kinds:
            stmt = stmt.where(DocumentModel.kind.in_([k.value for k in kinds]))
        stmt = stmt.order_by(DocumentModel.title)
        result = await self._s.execute(stmt)
        return [Document.model_validate(r) for r in result.scalars()]

    async def upsert(
        self,
        *,
        project_id: uuid.UUID,
        kind: DocumentKind,
        title: str,
        body: str,
        phases: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Document:
        result = await self._s.execute(
            select(DocumentModel).where(
                DocumentModel.project_id == project_id,
                DocumentModel.title == title,
            ),
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.kind = kind.value
            existing.body = body
            existing.phases = phases or []
            existing.metadata_ = metadata or {}
            await self._s.flush()
            await self._s.refresh(existing)
            return Document.model_validate(existing)
        row = DocumentModel(
            project_id=project_id,
            kind=kind.value,
            title=title,
            body=body,
            phases=phases or [],
            metadata_=metadata or {},
        )
        self._s.add(row)
        await self._s.flush()
        await self._s.refresh(row)
        return Document.model_validate(row)

    async def replace_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[dict[str, object]],
    ) -> int:
        await self._s.execute(
            delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id),
        )
        if not chunks:
            return 0
        await self._s.execute(
            pg_insert(DocumentChunkModel),
            [
                {
                    "document_id": document_id,
                    "chunk_index": c["chunk_index"],
                    "section_path": c.get("section_path"),
                    "text": c["text"],
                    "embedding": c.get("embedding"),
                    "metadata_": c.get("metadata", {}),
                }
                for c in chunks
            ],
        )
        return len(chunks)

    async def list_chunks_for_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        result = await self._s.execute(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index),
        )
        return [DocumentChunk.model_validate(r) for r in result.scalars()]
