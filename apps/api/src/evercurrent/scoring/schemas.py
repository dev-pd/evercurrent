"""Pydantic schemas for the scoring engine.

Strict mode so callers cannot smuggle in mistyped JSON. The schemas are
the engine's public contract: `ScoreInput` in, `ScoreResult` out, with a
breakdown that the dashboard renders as "why this is in your top 5."
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Urgency = Literal["critical", "high", "normal", "low"]


class ScoreInput(BaseModel):
    """Typed inputs to `engine.score`.

    Combines message-side, member-side, and project-side fields. The
    engine never touches the DB; every field a signal needs lives here.
    """

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
    """Clamped total plus the per-signal breakdown for audit/UI."""

    model_config = ConfigDict(strict=True, frozen=True)

    total: float
    breakdown: dict[str, float]
