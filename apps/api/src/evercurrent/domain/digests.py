"""Digest + feedback domain models."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import IntEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class FeedbackSignal(IntEnum):
    THUMBS_DOWN = -1
    THUMBS_UP = 1


def _coerce_signal(v: object) -> FeedbackSignal:
    if isinstance(v, FeedbackSignal):
        return v
    if isinstance(v, int):
        return FeedbackSignal(v)
    raise TypeError(f"cannot coerce {type(v).__name__} to FeedbackSignal")


FeedbackSignalField = Annotated[FeedbackSignal, BeforeValidator(_coerce_signal)]


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
    signal: FeedbackSignalField
    created_at: dt.datetime
