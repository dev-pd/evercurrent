"""Pydantic strict response models for MCP tools.

These are the contract between tools and agents. Strict mode means the
agent sees a typed shape, not a loose dict. Frozen means tool responses
are values, not mutable state. Each model carries the minimum fields
required to render a citation in a digest or chat answer (id, snippet,
source, posted_at where applicable).
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class MessageRef(BaseModel):
    """A reference to a single message, with enough context for a citation."""

    model_config = ConfigDict(strict=True, frozen=True)

    id: uuid.UUID
    channel: str
    author: str
    text: str
    posted_at: dt.datetime
    score: float | None = None


class ChunkRef(BaseModel):
    """A reference to a document chunk returned by semantic search."""

    model_config = ConfigDict(strict=True, frozen=True)

    document_id: uuid.UUID
    ordinal: int
    section: str | None
    text: str
    similarity: float


class CardRef(BaseModel):
    """A reference to a Knowledge Card (Phase 6).

    Until the `cards` table lands, `query_cards` returns this shape
    sourced from the `decisions` table as a placeholder.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    id: uuid.UUID
    kind: str
    summary: str
    status: str
    decided_at: dt.datetime | None = None


class ThreadContext(BaseModel):
    """A message thread: the root post + all its replies."""

    model_config = ConfigDict(strict=True, frozen=True)

    root: MessageRef
    replies: list[MessageRef]


class UserContext(BaseModel):
    """A project member's profile, used by the agent to personalise output."""

    model_config = ConfigDict(strict=True, frozen=True)

    membership_id: uuid.UUID
    display_name: str
    role: str
    owned_subsystems: list[str]
    topic_weights: dict[str, float]
