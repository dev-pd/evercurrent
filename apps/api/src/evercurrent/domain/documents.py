"""Document + chunk domain models."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


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
    # `from_attributes` reads `obj.metadata_` on ORM rows because SQLAlchemy
    # reserves `obj.metadata` for the table registry; the alias bridges them.
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
