"""Knowledge-card ORM models: cards + their sources (Phase 6)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from evercurrent.db.models.base import Base, _ts_default, _uuid_pk


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
