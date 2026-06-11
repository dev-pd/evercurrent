"""Focus model schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

FocusSource = Literal["role", "phase", "learned"]
FocusTrend = Literal["up", "flat", "down"]


class FocusTopic(BaseModel):
    model_config = ConfigDict(strict=True)

    topic: str
    label: str
    weight: float  # 0..1, relative focus strength
    sources: list[FocusSource]  # why this is in focus
    trend: FocusTrend  # recent movement from learned behaviour
