from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SubscriptionKind = Literal[
    "morning_digest",
    "urgent_immediate",
    "weekly_summary",
    "mention",
    "decision_affecting_subsystem",
]


class SubscriptionItem(BaseModel):
    model_config = ConfigDict(strict=True)

    kind: SubscriptionKind
    value: str | None = None
    enabled: bool = True


class SubscriptionsPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    items: Annotated[list[SubscriptionItem], Field(default_factory=list)]


class NotificationRow(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    membership_id: uuid.UUID
    kind: str
    channel: str
    payload: dict[str, Any]
    sent_at: dt.datetime
    opened_at: dt.datetime | None = None
    clicked_at: dt.datetime | None = None
