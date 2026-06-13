from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from evercurrent.db.models.base import Base, _ts_default, _uuid_pk


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
