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
    phase_concerns: dict[str, list[str]] = Field(default_factory=dict)
    milestones: list[dict[str, str]] = Field(default_factory=list)
    created_at: dt.datetime
    updated_at: dt.datetime


class Channel(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: Annotated[str, Field(pattern=r"^#?[a-z0-9-]+$", max_length=64)]
    description: str | None = None
    created_at: dt.datetime
