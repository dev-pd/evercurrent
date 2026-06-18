"""Signal shapes: the LLM draft (SignalDraft), the list/detail HTTP responses
(SignalListItem, SignalPage, SignalResponse), and their source references."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SignalKindT = Literal["decision", "risk", "question"]
SignalStatusT = Literal["open", "resolved", "dismissed"]
SourceKindT = Literal["message", "document_chunk", "pr"]


class SignalDraft(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    summary: str = Field(min_length=10, max_length=200)
    body: str = Field(min_length=20)
    affected_subsystems: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    decided_at: dt.datetime | None = None

    @field_validator("decided_at", mode="before")
    @classmethod
    def _coerce_decided_at(cls, v: object) -> object:
        # Sonnet returns decided_at as an ISO string ("2024-01-01T00:00:00Z");
        # strict mode would reject the str and force a wasted retry, so parse it
        # here. Unparseable / "null" -> None rather than failing the whole draft.
        if isinstance(v, str):
            text = v.strip()
            if not text or text.lower() == "null":
                return None
            try:
                return dt.datetime.fromisoformat(text)
            except ValueError:
                return None
        return v


class SignalSourceRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    source_kind: SourceKindT
    source_id: uuid.UUID
    snippet: str | None = None


class ResolveCheck(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    resolves: bool
    reason: str | None = None


class SignalListItem(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: SignalKindT
    summary: str
    status: SignalStatusT
    confidence: float
    decided_at: dt.datetime | None = None
    resolved_at: dt.datetime | None = None
    occurred_at: dt.datetime | None = None
    sources_count: int
    affected_subsystems: list[str] = []
    affected_roles: list[str] = []
    updated_at: dt.datetime


class SignalPage(BaseModel):
    model_config = ConfigDict(strict=True)

    items: list[SignalListItem]
    total: int
    limit: int
    offset: int


class SignalSourceDetail(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: SourceKindT
    channel: str | None = None
    author_display_name: str | None = None
    author_username: str | None = None
    ts: str | None = None
    text: str
    url: str | None = None


class SignalResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: SignalKindT
    summary: str
    body: str
    status: SignalStatusT
    confidence: float
    decided_at: dt.datetime | None = None
    affected_subsystems: list[str]
    affected_roles: list[str] = []
    sources: list[SignalSourceDetail]
    created_at: dt.datetime
    updated_at: dt.datetime
