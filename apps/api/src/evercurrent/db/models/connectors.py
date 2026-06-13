from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from evercurrent.db.models.base import Base, _ts_default, _uuid_pk


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

    __table_args__ = (Index("raw_events_dedupe_unique", "source", "external_id", unique=True),)
