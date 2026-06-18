"""The classifier's output shape (ClassificationResult) with a signal-field
consistency check, plus a neutral fallback used when the LLM output won't parse."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

UrgencyT = Literal["low", "normal", "high", "critical"]
SignalKindT = Literal["decision", "risk", "question"]


class ClassificationResult(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    topic: str | None
    urgency: UrgencyT
    entities: list[str]
    affected_roles: list[str]
    should_create_signal: bool
    signal_kind: SignalKindT | None
    signal_summary: str | None
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_signal_fields_consistent(self) -> Self:
        if self.should_create_signal:
            if self.signal_kind is None or self.signal_summary is None:
                msg = (
                    "should_create_signal=True requires both signal_kind and "
                    "signal_summary to be non-null"
                )
                raise ValueError(msg)
        elif self.signal_kind is not None or self.signal_summary is not None:
            msg = (
                "should_create_signal=False requires both signal_kind and signal_summary to be null"
            )
            raise ValueError(msg)
        return self


def fallback_classification() -> ClassificationResult:
    return ClassificationResult(
        topic=None,
        urgency="normal",
        entities=[],
        affected_roles=[],
        should_create_signal=False,
        signal_kind=None,
        signal_summary=None,
        confidence=0.0,
    )
