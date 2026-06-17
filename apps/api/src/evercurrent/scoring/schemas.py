"""Scoring I/O contracts: the signal bundle for one (member, message) pair
and the resulting score plus its per-signal breakdown."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Urgency = Literal["critical", "high", "normal", "low"]


class ScoreInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    member_role: str
    owned_subsystems: list[str] = Field(default_factory=list)
    topic_weights: dict[str, float] = Field(default_factory=dict)

    message_topic: str | None = None
    message_entities: list[str] = Field(default_factory=list)
    message_urgency: Urgency | None = None
    message_affected_roles: list[str] = Field(default_factory=list)

    author_role: str
    phase_concerns: list[str] = Field(default_factory=list)


class ScoreResult(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    total: float
    breakdown: dict[str, float]
