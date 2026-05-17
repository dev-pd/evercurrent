"""Message + tag domain models."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Message(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    channel_id: uuid.UUID
    author_id: uuid.UUID
    thread_root_id: uuid.UUID | None = None
    day: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(min_length=1)]
    ts: dt.datetime
    reactions: dict[str, int] = Field(default_factory=dict)
    created_at: dt.datetime


class MessageTag(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    message_id: uuid.UUID
    topic: Annotated[str, Field(min_length=1, max_length=64)]
    urgency: Urgency
    affected_roles: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    raw_tag: dict[str, object] = Field(default_factory=dict)
    tagged_at: dt.datetime


class EnrichedMessage(BaseModel):
    """A message joined with its tag (if enrichment has run yet)."""

    model_config = ConfigDict(strict=True)

    message: Message
    tag: MessageTag | None = None
    author_username: str
    channel_name: str

    @property
    def has_tag(self) -> bool:
        return self.tag is not None
