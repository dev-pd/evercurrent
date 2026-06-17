from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

UrgencyT = Literal["low", "normal", "high", "critical"]
CardKindT = Literal["decision", "risk", "question"]


class RouterDecision(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    topic: str | None
    urgency: UrgencyT
    entities: list[str]
    affected_roles: list[str]
    should_create_card: bool
    card_kind: CardKindT | None
    card_summary: str | None
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_card_fields_consistent(self) -> Self:
        if self.should_create_card:
            if self.card_kind is None or self.card_summary is None:
                msg = (
                    "should_create_card=True requires both card_kind and "
                    "card_summary to be non-null"
                )
                raise ValueError(msg)
        elif self.card_kind is not None or self.card_summary is not None:
            msg = "should_create_card=False requires both card_kind and card_summary to be null"
            raise ValueError(msg)
        return self


def fallback_decision() -> RouterDecision:
    return RouterDecision(
        topic=None,
        urgency="normal",
        entities=[],
        affected_roles=[],
        should_create_card=False,
        card_kind=None,
        card_summary=None,
        confidence=0.0,
    )
