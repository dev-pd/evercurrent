from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from evercurrent.db.models.base import Base, _ts_default, _uuid_pk


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
