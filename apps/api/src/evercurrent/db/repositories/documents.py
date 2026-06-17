from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Document as DocumentModel
from evercurrent.db.models import DocumentChunk as DocumentChunkModel


class DocumentKind(StrEnum):
    PRD = "prd"
    BOM = "bom"
    ECO_LOG = "eco_log"
    TEST_REPORT_THERMAL = "test_report_thermal"
    TEST_REPORT_DROP = "test_report_drop"
    OTHER = "other"


def _coerce_kind(v: object) -> DocumentKind:
    if isinstance(v, DocumentKind):
        return v
    if isinstance(v, str):
        return DocumentKind(v)
    raise TypeError(f"cannot coerce {type(v).__name__} to DocumentKind")


DocumentKindField = Annotated[DocumentKind, BeforeValidator(_coerce_kind)]


class Document(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: DocumentKindField
    title: Annotated[str, Field(min_length=1, max_length=255)]
    body: str
    phases: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict, alias="metadata_")
    created_at: dt.datetime


class DocumentChunk(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: Annotated[int, Field(ge=0)]
    section_path: str | None = None
    text: str
    embedding: list[float] | None = None
    metadata: dict[str, object] = Field(default_factory=dict, alias="metadata_")
    created_at: dt.datetime


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
