"""Document routes."""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.api.deps import SessionDep
from evercurrent.api.schemas import DocumentResponse
from evercurrent.db.repositories import DocumentRepository, ProjectRepository
from evercurrent.ingestion.tasks import ingest_pdf_bytes

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_EXCERPT_CHARS = 280
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class UploadResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    document_id: str | None
    chunks: int
    skipped: str | None = None


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    session: SessionDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    phase: Annotated[str | None, Query()] = None,
) -> list[DocumentResponse]:
    """List project documents. Optional `phase` filters to docs whose
    `phases` array contains the requested phase (or have an empty phases
    list, meaning all-phase docs)."""
    if project_id is None:
        projects = await ProjectRepository(session).list_all()
        if not projects:
            return []
        project_id = projects[0].id
    docs = await DocumentRepository(session).list_for_project(project_id)
    out: list[DocumentResponse] = []
    for d in docs:
        if phase and d.phases and phase not in d.phases:
            continue
        excerpt = d.body[:_EXCERPT_CHARS]
        if len(d.body) > _EXCERPT_CHARS:
            excerpt += "…"
        out.append(
            DocumentResponse(
                id=d.id,
                project_id=d.project_id,
                kind=d.kind.value,
                title=d.title,
                phases=d.phases,
                body_excerpt=excerpt,
                chars=len(d.body),
            ),
        )
    return out


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    session: SessionDep,
    file: Annotated[UploadFile, File(description="PDF file to ingest")],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> UploadResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="only application/pdf is supported",
        )
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")
    if len(pdf_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds {_MAX_UPLOAD_BYTES} bytes",
        )

    query = (
        text("SELECT org_id FROM projects WHERE id = :pid")
        if project_id is not None
        else text("SELECT org_id FROM projects ORDER BY name LIMIT 1")
    )
    params = {"pid": str(project_id)} if project_id is not None else {}
    row = (await session.execute(query, params)).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no project found; create one first",
        )
    org_id = uuid.UUID(str(row[0]))

    title = file.filename or "untitled.pdf"
    external_id = f"upload-{hashlib.sha256(pdf_bytes).hexdigest()[:16]}"

    result = await ingest_pdf_bytes(
        org_id=org_id,
        source="upload",
        external_id=external_id,
        title=title,
        pdf_bytes=pdf_bytes,
    )
    return UploadResponse(
        document_id=result.get("document_id"),
        chunks=result.get("chunks", 0),
        skipped=result.get("skipped"),
    )
