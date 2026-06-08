"""Pydantic schemas for the digest agent.

`DigestDraft` is Sonnet's structured output. The agent renders prompts,
calls the LLM, parses the JSON response into a `DigestDraft`, and then
the repository persists it as a `digests` row.

`MemberProfile`, `ProjectSnapshot`, `ScoredItem`, `CardSummary`, and
`PriorDigest` are the strongly-typed building blocks of the prompt
context — they decouple the agent from raw SQL row shapes.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class MemberProfile(BaseModel):
    """The member the digest is being written for."""

    model_config = ConfigDict(strict=True, frozen=True)

    project_member_id: uuid.UUID
    display_name: str
    role: str
    timezone: str
    owned_subsystems: list[str] = Field(default_factory=list)
    topic_weights: dict[str, float] = Field(default_factory=dict)


class ProjectSnapshot(BaseModel):
    """Project context the digest writer needs."""

    model_config = ConfigDict(strict=True, frozen=True)

    project_id: uuid.UUID
    name: str
    current_phase: str
    phase_concerns: list[str] = Field(default_factory=list)


class ScoredItem(BaseModel):
    """One high-scoring message for the member."""

    model_config = ConfigDict(strict=True, frozen=True)

    message_id: uuid.UUID
    score: float
    topic: str | None = None
    urgency: str | None = None
    channel: str | None = None
    author: str | None = None
    text: str
    posted_at: dt.datetime


class CardSummary(BaseModel):
    """One open Card affecting one of the member's subsystems."""

    model_config = ConfigDict(strict=True, frozen=True)

    card_id: uuid.UUID
    kind: str
    summary: str
    status: str
    affected_subsystems: list[str] = Field(default_factory=list)
    updated_at: dt.datetime


class PriorDigest(BaseModel):
    """A previously-written digest, included for continuity."""

    model_config = ConfigDict(strict=True, frozen=True)

    day_index: int
    content_md: str


class DigestContext(BaseModel):
    """Everything the agent needs to draft one personalised digest."""

    model_config = ConfigDict(strict=True, frozen=True)

    member: MemberProfile
    project: ProjectSnapshot
    day_index: int
    top_scored_items: list[ScoredItem] = Field(default_factory=list)
    open_cards: list[CardSummary] = Field(default_factory=list)
    prior_digests: list[PriorDigest] = Field(default_factory=list)


SectionBucketT = Literal["top_priority", "watch_outs", "fyi"]


class DigestDraft(BaseModel):
    """Sonnet's structured output for one digest."""

    model_config = ConfigDict(strict=True)

    content_md: Annotated[str, Field(min_length=20)]
    card_ids: list[uuid.UUID] = Field(default_factory=list)
    message_ids: list[uuid.UUID] = Field(default_factory=list)
    section_buckets: dict[str, list[uuid.UUID]] = Field(default_factory=dict)
