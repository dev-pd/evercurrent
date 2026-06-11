"""SQLAlchemy 2.0 declarative ORM models for EverCurrent.

These map 1:1 to the tables created by the initial Alembic migration.
Domain models in `evercurrent.domain.*` are Pydantic and live behind the
repository boundary — never import these models above the `db/` package.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all EverCurrent ORM models."""

    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB,
        list[str]: ARRAY(Text),
    }


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


def _ts_default() -> Mapped[dt.datetime]:
    return mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


# -----------------------------------------------------------------------------
# Project + people
# -----------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    current_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    start_date: Mapped[dt.date] = mapped_column(
        Date,
        nullable=False,
        server_default="2026-05-11",
    )
    phase_concerns: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    milestones: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    created_at: Mapped[dt.datetime] = _ts_default()
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    users: Mapped[list[User]] = relationship(back_populates="project", cascade="all, delete-orphan")
    channels: Mapped[list[Channel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[list[Decision]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    owned_subsystems: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    owned_parts: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    topic_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[dt.datetime] = _ts_default()

    project: Mapped[Project] = relationship(back_populates="users")
    messages: Mapped[list[Message]] = relationship(back_populates="author")
    feedback: Mapped[list[Feedback]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_users_project_username", "project_id", "username", unique=True),)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = _ts_default()

    project: Mapped[Project] = relationship(back_populates="channels")
    messages: Mapped[list[Message]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_channels_project_name", "project_id", "name", unique=True),)


# -----------------------------------------------------------------------------
# Messages + enrichment
# -----------------------------------------------------------------------------


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_root_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[dt.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    reactions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[dt.datetime] = _ts_default()

    project: Mapped[Project] = relationship()
    channel: Mapped[Channel] = relationship(back_populates="messages")
    author: Mapped[User] = relationship(back_populates="messages")
    tags: Mapped[MessageTag | None] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (Index("ix_messages_project_day_ts", "project_id", "day", "ts"),)


class MessageTag(Base):
    __tablename__ = "message_tags"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(16), nullable=False)
    affected_roles: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    entities: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    raw_tag: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    tagged_at: Mapped[dt.datetime] = _ts_default()

    message: Mapped[Message] = relationship(back_populates="tags")

    __table_args__ = (
        CheckConstraint(
            "urgency IN ('low','medium','high','critical')",
            name="ck_message_tags_urgency",
        ),
    )


# -----------------------------------------------------------------------------
# Documents + RAG chunks
# -----------------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    phases: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[dt.datetime] = _ts_default()
    ingested_at: Mapped[dt.datetime] = _ts_default()

    project: Mapped[Project] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(512), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[dt.datetime] = _ts_default()

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_document_chunks_doc_chunkidx",
            "document_id",
            "chunk_index",
            unique=True,
        ),
    )


# -----------------------------------------------------------------------------
# Decisions
# -----------------------------------------------------------------------------


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False)
    decided_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        index=True,
    )
    source_message_ids: Mapped[list[str]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    affected_subsystems: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = _ts_default()

    project: Mapped[Project] = relationship(back_populates="decisions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed','decided','implemented','reverted')",
            name="ck_decisions_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_decisions_confidence_range",
        ),
    )


# -----------------------------------------------------------------------------
# Digests + feedback
# -----------------------------------------------------------------------------


class Digest(Base):
    """Phase 8 digests: one row per (project_member, day_index).

    Replaces the legacy (user_id, day, phase) shape. Citations are split
    into `card_ids` and `message_ids` arrays so the dashboard does not
    have to re-parse markdown.
    """

    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    card_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    generated_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        Index(
            "digests_member_day_unique",
            "project_member_id",
            "day_index",
            unique=True,
        ),
        Index("digests_org_idx", "org_id"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = _ts_default()

    user: Mapped[User] = relationship(back_populates="feedback")

    __table_args__ = (CheckConstraint("signal IN (-1, 1)", name="ck_feedback_signal"),)


# -----------------------------------------------------------------------------
# Multi-tenancy (Phase 2)
# -----------------------------------------------------------------------------


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    auth0_org_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="free")
    region: Mapped[str] = mapped_column(Text, nullable=False, server_default="us-east")
    itar: Mapped[bool] = mapped_column(
        nullable=False,
        server_default="false",
    )
    created_at: Mapped[dt.datetime] = _ts_default()


class OrgMembership(Base):
    __tablename__ = "org_memberships"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    auth0_user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    slack_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="member")
    eng_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    owned_subsystems: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    topic_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    quiet_start: Mapped[dt.time | None] = mapped_column(nullable=True)
    quiet_end: Mapped[dt.time | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        CheckConstraint("role IN ('admin','member')", name="org_memberships_role_check"),
        Index("org_memberships_unique", "org_id", "auth0_user_id", unique=True),
    )


# -----------------------------------------------------------------------------
# Connectors + raw event ingest (Phase 3)
# -----------------------------------------------------------------------------


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    external_team_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials_secret: Mapped[str] = mapped_column(Text, nullable=False)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    installed_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        Index("connectors_org_kind_unique", "org_id", "kind", unique=True),
        Index("connectors_team_lookup_idx", "kind", "external_team_id"),
    )


class ConnectorChannel(Base):
    __tablename__ = "connector_channels"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    ingest: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        Index(
            "connector_channels_unique",
            "connector_id",
            "external_id",
            unique=True,
        ),
    )


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        Index("raw_events_dedupe_unique", "source", "external_id", unique=True),
    )


# -----------------------------------------------------------------------------
# Scoring (Phase 7)
# -----------------------------------------------------------------------------


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    computed_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        Index(
            "ix_scores_project_member_message_unique",
            "project_member_id",
            "message_id",
            unique=True,
        ),
        Index("ix_scores_member_score_desc", "project_member_id", "score"),
        Index("ix_scores_org", "org_id"),
    )


# -----------------------------------------------------------------------------
# Knowledge cards (Phase 6)
# -----------------------------------------------------------------------------


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    owner_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    triggering_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    affected_subsystems: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = _ts_default()
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('decision','risk','question')",
            name="ck_cards_kind",
        ),
        CheckConstraint(
            "status IN ('open','resolved','dismissed')",
            name="ck_cards_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_cards_confidence_range",
        ),
        Index("cards_org_idx", "org_id"),
        Index("cards_project_kind_idx", "project_id", "kind"),
    )


class CardSource(Base):
    __tablename__ = "card_sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('message','document_chunk','pr')",
            name="ck_card_sources_kind",
        ),
        Index("card_sources_card_idx", "card_id"),
        Index("card_sources_lookup_idx", "source_kind", "source_id"),
    )


# -----------------------------------------------------------------------------
# Notifications + subscriptions (Phase 11)
# -----------------------------------------------------------------------------


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = _ts_default()

    __table_args__ = (
        CheckConstraint(
            "kind IN ('morning_digest','urgent_immediate','weekly_summary',"
            "'mention','decision_affecting_subsystem')",
            name="ck_subscriptions_kind",
        ),
        Index("subscriptions_membership_idx", "membership_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[dt.datetime] = _ts_default()
    opened_at: Mapped[dt.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    clicked_at: Mapped[dt.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("notifications_org_idx", "org_id"),
    )


# Used by Alembic via target_metadata.
metadata = Base.metadata
