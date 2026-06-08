"""Pydantic strict schemas for the ingestion pipeline."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class DocClassification(BaseModel):
    """Haiku-judged verdict on whether a doc is decision-bearing."""

    model_config = ConfigDict(strict=True)

    is_decision: bool
    kind: Literal["eco", "test_report", "prd", "bom", "other"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    rationale: Annotated[str, Field(max_length=2_000)]
