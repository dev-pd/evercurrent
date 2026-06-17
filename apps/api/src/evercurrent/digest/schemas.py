"""Digest shapes: the persisted DigestRecord, the context fed to the LLM
(member/project/scored items/cards), and the parsed DigestDraft it returns."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class DigestRecord(BaseModel):
    """A persisted digest as read back from the database."""

    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    project_member_id: uuid.UUID
    day_index: Annotated[int, Field(ge=0)]
    phase: Annotated[str, Field(min_length=1, max_length=64)]
    content_md: str
    card_ids: list[uuid.UUID] = Field(default_factory=list)
    message_ids: list[uuid.UUID] = Field(default_factory=list)
    generated_at: dt.datetime


class DigestMessageRow(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    channel: str | None
    author_display_name: str | None
    posted_at: dt.datetime | None
    text: str | None
    urgency: str | None


def _coerce_uuid(v: object) -> uuid.UUID:
    if isinstance(v, uuid.UUID):
        return v
    if isinstance(v, str):
        return uuid.UUID(v)
    msg = f"cannot coerce {type(v).__name__} to UUID"
    raise TypeError(msg)


def _coerce_uuid_list(v: object) -> list[uuid.UUID]:
    if not isinstance(v, list):
        msg = f"expected list, got {type(v).__name__}"
        raise TypeError(msg)
    return [_coerce_uuid(item) for item in v]


def _coerce_uuid_dict(v: object) -> dict[str, list[uuid.UUID]]:
    if not isinstance(v, dict):
        msg = f"expected dict, got {type(v).__name__}"
        raise TypeError(msg)
    out: dict[str, list[uuid.UUID]] = {}
    for k, vals in v.items():
        out[str(k)] = _coerce_uuid_list(vals)
    return out


UUIDList = Annotated[list[uuid.UUID], BeforeValidator(_coerce_uuid_list)]
UUIDDict = Annotated[
    dict[str, list[uuid.UUID]],
    BeforeValidator(_coerce_uuid_dict),
]


class MemberProfile(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    project_member_id: uuid.UUID
    display_name: str
    role: str
    timezone: str
    owned_subsystems: list[str] = Field(default_factory=list)
    topic_weights: dict[str, float] = Field(default_factory=dict)


class ProjectSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    project_id: uuid.UUID
    name: str
    current_phase: str
    phase_concerns: list[str] = Field(default_factory=list)


class ScoredItem(BaseModel):
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
    model_config = ConfigDict(strict=True, frozen=True)

    card_id: uuid.UUID
    kind: str
    summary: str
    status: str
    affected_subsystems: list[str] = Field(default_factory=list)
    updated_at: dt.datetime


class PriorDigest(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    day_index: int
    content_md: str


class DigestContext(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    member: MemberProfile
    project: ProjectSnapshot
    day_index: int
    top_scored_items: list[ScoredItem] = Field(default_factory=list)
    open_cards: list[CardSummary] = Field(default_factory=list)
    prior_digests: list[PriorDigest] = Field(default_factory=list)


SectionBucketT = Literal["top_priority", "watch_outs", "fyi"]


class DigestDraft(BaseModel):
    model_config = ConfigDict(strict=True)

    content_md: Annotated[str, Field(min_length=20)]
    card_ids: UUIDList = Field(default_factory=list)
    message_ids: UUIDList = Field(default_factory=list)
    section_buckets: UUIDDict = Field(default_factory=dict)
