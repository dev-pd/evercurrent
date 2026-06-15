from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CardKindT = Literal["decision", "risk", "question"]
CardStatusT = Literal["open", "resolved", "dismissed"]
SourceKindT = Literal["message", "document_chunk", "pr"]


class CardDraft(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    summary: str = Field(min_length=10, max_length=200)
    body: str = Field(min_length=20)
    affected_subsystems: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    decided_at: dt.datetime | None = None


class CardSourceRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    source_kind: SourceKindT
    source_id: uuid.UUID
    snippet: str | None = None


class CardListItem(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: CardKindT
    summary: str
    status: CardStatusT
    confidence: float
    decided_at: dt.datetime | None = None
    occurred_at: dt.datetime | None = None
    sources_count: int
    affected_subsystems: list[str] = []
    updated_at: dt.datetime


class CardSourceDetail(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: SourceKindT
    channel: str | None = None
    author_display_name: str | None = None
    author_username: str | None = None
    ts: str | None = None
    text: str
    url: str | None = None


class CardResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: CardKindT
    summary: str
    body: str
    status: CardStatusT
    confidence: float
    decided_at: dt.datetime | None = None
    affected_subsystems: list[str]
    sources: list[CardSourceDetail]
    created_at: dt.datetime
    updated_at: dt.datetime


class CardFeedbackPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    signal: Literal[-1, 1]
    topic: str | None = None
