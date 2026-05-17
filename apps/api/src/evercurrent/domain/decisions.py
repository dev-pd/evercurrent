"""Decision domain model."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    DECIDED = "decided"
    IMPLEMENTED = "implemented"
    REVERTED = "reverted"


def _coerce_status(v: object) -> DecisionStatus:
    if isinstance(v, DecisionStatus):
        return v
    if isinstance(v, str):
        return DecisionStatus(v)
    raise TypeError(f"cannot coerce {type(v).__name__} to DecisionStatus")


DecisionStatusField = Annotated[DecisionStatus, BeforeValidator(_coerce_status)]


class Decision(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    summary: Annotated[str, Field(min_length=1)]
    rationale: str | None = None
    decided_by: Annotated[str, Field(min_length=1, max_length=128)]
    decided_at: dt.datetime
    source_message_ids: list[uuid.UUID] = Field(default_factory=list)
    affected_subsystems: list[str] = Field(default_factory=list)
    status: DecisionStatusField
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    created_at: dt.datetime
