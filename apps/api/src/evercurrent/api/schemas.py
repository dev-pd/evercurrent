"""Pydantic request + response schemas for the HTTP API.

These are wire-level shapes; domain models stay internal.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    name: str
    current_phase: str
    current_day: int
    phase_concerns: dict[str, list[str]]
    milestones: list[dict[str, str]]


class UserResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    project_id: uuid.UUID
    username: str
    display_name: str
    role: str
    owned_subsystems: list[str]
    owned_parts: list[str]
    topic_weights: dict[str, float]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    title: str
    phases: list[str]
    body_excerpt: str
    chars: int


class DigestItem(BaseModel):
    """One source message cited by the digest, joined with its tag."""

    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    channel: str
    author_username: str
    author_display_name: str
    day: int
    ts: dt.datetime
    text: str
    topic: str | None = None
    urgency: str | None = None


class DigestResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    user_id: uuid.UUID
    day: int
    phase: str
    content_md: str
    item_message_ids: list[uuid.UUID]
    items: list[DigestItem] = Field(default_factory=list)
    generated_at: dt.datetime


class GenerateDigestsResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    job_id: str
    day: int


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: uuid.UUID
    message_id: uuid.UUID
    signal: Annotated[Literal[-1, 1], Field(description="-1 thumbs down, +1 thumbs up")]
    topic: str | None = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: uuid.UUID
    topic_weights: dict[str, float]


class ChangePhaseRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    phase: Annotated[str, Field(min_length=1, max_length=32)]


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    query: Annotated[str, Field(min_length=1, max_length=4000)]


class DecisionResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    summary: str
    rationale: str | None
    decided_by: str
    decided_at: dt.datetime
    source_message_ids: list[uuid.UUID]
    affected_subsystems: list[str]
    status: str
    confidence: float


class MessageResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    channel: str
    author_username: str
    day: int
    text: str
    ts: dt.datetime
    thread_root_id: uuid.UUID | None
    topic: str | None = None
    urgency: str | None = None


class TimelineResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: uuid.UUID
    digests: list[DigestResponse]


class SimulationStatusResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    current_day: int
    last_job_id: str | None = None
