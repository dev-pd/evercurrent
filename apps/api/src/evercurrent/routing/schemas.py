"""Pydantic schemas for the Router agent.

`RouterDecision` is the agent's structured output. We persist topic,
urgency, entities, and affected_roles into `message_tags`; we read
`should_create_card`, `card_kind`, `card_summary`, and `confidence`
to decide whether to enqueue `build_card`.

Cross-field invariant: if `should_create_card` is True, both
`card_kind` and `card_summary` must be present. We enforce that with a
`model_validator(mode='after')` so the agent loop catches drift via a
`ValidationError` and triggers the single-retry path.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

UrgencyT = Literal["low", "normal", "high", "critical"]
CardKindT = Literal["decision", "risk", "question"]


class RouterDecision(BaseModel):
    """Structured output from the Router agent."""

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
            msg = (
                "should_create_card=False requires both card_kind and "
                "card_summary to be null"
            )
            raise ValueError(msg)
        return self


def fallback_decision() -> RouterDecision:
    """Uncategorised fallback when the LLM cannot produce a valid decision."""
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
