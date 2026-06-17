"""HTTP boundary shapes shared across routes. Request/response bodies for the
project endpoints; per-resource shapes live next to their own router."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ProjectResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    name: str
    current_phase: str
    current_day: int
    phase_concerns: dict[str, list[str]]
    milestones: list[dict[str, str]]


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    name: Annotated[str, Field(min_length=1, max_length=255)]
    current_phase: Annotated[str, Field(min_length=1, max_length=32)]
    start_date: Annotated[dt.date, Field(strict=False)]
    phase_concerns: dict[str, list[str]] = Field(default_factory=dict)
