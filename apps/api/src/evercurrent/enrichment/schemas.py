"""Schemas for message enrichment output."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from evercurrent.domain.messages import Urgency


def _coerce_urgency(v: object) -> Urgency:
    if isinstance(v, Urgency):
        return v
    if isinstance(v, str):
        return Urgency(v)
    raise TypeError(f"cannot coerce {type(v).__name__} to Urgency")


class MessageTagPayload(BaseModel):
    """Raw tag payload from the LLM (or heuristic). One per input message."""

    model_config = ConfigDict(strict=True)

    topic: Annotated[str, Field(min_length=1, max_length=64)]
    urgency: Annotated[Urgency, BeforeValidator(_coerce_urgency)]
    affected_roles: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)


VALID_TOPICS = (
    "supply_chain_disruption",
    "quality_issue",
    "design_change",
    "firmware_bug",
    "test_result",
    "schedule_risk",
    "eco",
    "supplier_issue",
    "thermal",
    "mechanical",
    "electrical",
    "decision",
    "compliance",
    "fyi",
)
