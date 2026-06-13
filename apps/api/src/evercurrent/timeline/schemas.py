from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

PhaseStatus = Literal["done", "active", "upcoming"]
LaneTone = Literal["primary", "muted"]


class PhaseBlock(BaseModel):
    model_config = ConfigDict(strict=True)

    label: str
    start_month: float
    end_month: float
    status: PhaseStatus


class LaneSegment(BaseModel):
    model_config = ConfigDict(strict=True)

    start: float
    end: float
    tone: LaneTone


class Lane(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    segments: list[LaneSegment]
    marker: float


class TimelineProjection(BaseModel):
    model_config = ConfigDict(strict=True)

    project_id: uuid.UUID
    project_name: str
    current_phase: str
    current_day: int
    start_date: str
    months: list[str]
    phases: list[PhaseBlock]
    lanes: list[Lane]
    summary: str
    fcs_label: str
    progress_pct: int
