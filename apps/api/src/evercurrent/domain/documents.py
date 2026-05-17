"""Document + chunk domain models."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DocumentKind(StrEnum):
    PRD = "prd"
    BOM = "bom"
    ECO_LOG = "eco_log"
    TEST_REPORT_THERMAL = "test_report_thermal"
    TEST_REPORT_DROP = "test_report_drop"
    OTHER = "other"


class Document(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: DocumentKind
    title: Annotated[str, Field(min_length=1, max_length=255)]
    body: str
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: dt.datetime


class DocumentChunk(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: Annotated[int, Field(ge=0)]
    section_path: str | None = None
    text: str
    embedding: list[float] | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: dt.datetime
