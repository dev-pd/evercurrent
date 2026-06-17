"""Shapes returned by the agent tools (thread context, user context, etc.) that
the agent loop serializes back into tool_result content."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class MessageRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: uuid.UUID
    channel: str
    author: str
    text: str
    posted_at: dt.datetime
    score: float | None = None


class ChunkRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    document_id: uuid.UUID
    ordinal: int
    section: str | None
    text: str
    similarity: float


class CardRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: uuid.UUID
    kind: str
    summary: str
    status: str
    affected_subsystems: list[str] = []
    decided_at: dt.datetime | None = None


class ThreadContext(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    root: MessageRef
    replies: list[MessageRef]


class UserContext(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    membership_id: uuid.UUID
    display_name: str
    role: str
    owned_subsystems: list[str]
    topic_weights: dict[str, float]
