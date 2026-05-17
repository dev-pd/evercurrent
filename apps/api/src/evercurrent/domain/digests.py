"""Digest + feedback domain models."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import IntEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class FeedbackSignal(IntEnum):
    THUMBS_DOWN = -1
    THUMBS_UP = 1


class Digest(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    day: Annotated[int, Field(ge=1)]
    content_md: str
    item_message_ids: list[uuid.UUID] = Field(default_factory=list)
    generated_at: dt.datetime


class Feedback(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    message_id: uuid.UUID
    signal: FeedbackSignal
    created_at: dt.datetime
