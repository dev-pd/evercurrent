"""Schemas for the decision extractor's LLM output."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from evercurrent.domain.decisions import DecisionStatus


def _coerce_status(v: object) -> DecisionStatus:
    if isinstance(v, DecisionStatus):
        return v
    if isinstance(v, str):
        return DecisionStatus(v)
    raise TypeError(f"cannot coerce {type(v).__name__} to DecisionStatus")


def _coerce_dt(v: object) -> dt.datetime:
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, str):
        parsed = dt.datetime.fromisoformat(v)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed
    raise TypeError(f"cannot coerce {type(v).__name__} to datetime")


class ExtractedDecision(BaseModel):
    """One decision from a message window. Persisted via DecisionRepository."""

    model_config = ConfigDict(strict=True)

    summary: Annotated[str, Field(min_length=1)]
    rationale: str | None = None
    decided_by: Annotated[str, Field(min_length=1, max_length=128)]
    decided_at: Annotated[dt.datetime, BeforeValidator(_coerce_dt)]
    source_message_ids: list[str] = Field(default_factory=list)
    affected_subsystems: list[str] = Field(default_factory=list)
    status: Annotated[DecisionStatus, BeforeValidator(_coerce_status)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
