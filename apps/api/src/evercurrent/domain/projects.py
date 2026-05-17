"""Project + channel domain models."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class PhasePolicy(BaseModel):
    """Phase-aware scoring policy. Concerns and weights per project phase."""

    model_config = ConfigDict(strict=True)

    concerns: dict[str, list[str]] = Field(default_factory=dict)
    phase_weights: dict[str, float] = Field(default_factory=dict)


class Project(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    name: Annotated[str, Field(min_length=1, max_length=255)]
    current_phase: Annotated[str, Field(min_length=1, max_length=32)]
    current_day: Annotated[int, Field(ge=1)]
    start_date: dt.date
    phase_concerns: dict[str, list[str]] = Field(default_factory=dict)
    milestones: list[dict[str, str]] = Field(default_factory=list)
    created_at: dt.datetime
    updated_at: dt.datetime

    def date_for_day(self, day: int) -> dt.date:
        """Return the calendar date this ordinal day maps to."""
        return self.start_date + dt.timedelta(days=day - 1)

    @property
    def today_day(self) -> int:
        """Ordinal day for the wall-clock today, clamped to >=1."""
        delta = (dt.datetime.now(dt.UTC).date() - self.start_date).days
        return max(1, delta + 1)


class Channel(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: Annotated[str, Field(pattern=r"^#?[a-z0-9-]+$", max_length=64)]
    description: str | None = None
    created_at: dt.datetime
