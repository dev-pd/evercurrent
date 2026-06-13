from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

FocusSource = Literal["role", "phase", "learned"]
FocusTrend = Literal["up", "flat", "down"]


class FocusTopic(BaseModel):
    model_config = ConfigDict(strict=True)

    topic: str
    label: str
    weight: float
    sources: list[FocusSource]
    trend: FocusTrend
