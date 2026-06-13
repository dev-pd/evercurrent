"""Project + channel ORM models."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from evercurrent.db.models.base import Base, _ts_default, _uuid_pk

if TYPE_CHECKING:
    from evercurrent.db.models.documents import Document
    from evercurrent.db.models.messages import Message
    from evercurrent.db.models.users import User


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
