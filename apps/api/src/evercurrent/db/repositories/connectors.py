"""SQL for connectors: list with ingest counts, channel-ingest toggle, and the
idempotent disconnect that cascade-purges the source's ingested data + members.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db import models


class ConnectorSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: str
    status: str
    external_team_id: str | None
    channels_count: int
    message_count: int


class ConnectorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_with_counts(self, *, org_id: uuid.UUID) -> list[ConnectorSummary]:
        rows = (
            (
                await self._s.execute(
                    select(models.Connector).where(models.Connector.org_id == org_id)
                )
            )
            .scalars()
            .all()
        )
        out: list[ConnectorSummary] = []
        for row in rows:
            channel_count = (
                await self._s.execute(
                    select(func.count())
                    .select_from(models.ConnectorChannel)
                    .where(models.ConnectorChannel.connector_id == row.id),
                )
            ).scalar_one()
            # What this source has ingested: Slack -> messages, Dropbox -> documents.
            if row.kind == "dropbox":
                item_count = (
                    await self._s.execute(
                        text(
                            "SELECT count(*) FROM documents "
                            "WHERE org_id = :org AND source = 'dropbox'",
                        ),
                        {"org": str(org_id)},
                    )
                ).scalar_one()
            else:
                item_count = (
                    await self._s.execute(
                        text("SELECT count(*) FROM messages WHERE org_id = :org AND source = :src"),
                        {"org": str(org_id), "src": row.kind},
                    )
                ).scalar_one()
            out.append(
                ConnectorSummary(
                    id=row.id,
                    kind=row.kind,
                    status=row.status,
                    external_team_id=row.external_team_id,
                    channels_count=int(channel_count),
                    message_count=int(item_count),
                ),
            )
        return out

    async def dropbox_connector_ids_for_account(self, account: str) -> list[uuid.UUID]:
        rows = (
            (
                await self._s.execute(
                    select(models.Connector.id).where(
                        models.Connector.kind == "dropbox",
                        models.Connector.external_team_id == account,
                    ),
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def slack_connector_exists(self, connector_id: uuid.UUID) -> bool:
        row = (
            await self._s.execute(
                select(models.Connector.id).where(
                    models.Connector.id == connector_id,
                    models.Connector.kind == "slack",
                ),
            )
        ).first()
        return row is not None

    async def set_channel_ingest(
        self,
        *,
        connector_id: uuid.UUID,
        external_id: str,
        ingest: bool,
    ) -> bool:
        row = (
            await self._s.execute(
                select(models.ConnectorChannel).where(
                    models.ConnectorChannel.connector_id == connector_id,
                    models.ConnectorChannel.external_id == external_id,
                ),
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        row.ingest = ingest
        return True

    async def disconnect(self, *, connector_id: uuid.UUID, org_id: uuid.UUID) -> dict[str, str]:
        """Idempotent: removes the connector + its ingested data + provisioned
        members. An already-gone connector is the desired end state, not an error.
        """
        connector = (
            await self._s.execute(
                select(models.Connector).where(
                    models.Connector.id == connector_id,
                    models.Connector.org_id == org_id,
                ),
            )
        ).scalar_one_or_none()
        if connector is None:
            return {"status": "not_connected", "kind": "unknown"}
        kind = connector.kind
        await self._s.delete(connector)
        await self._purge_source_data(org_id=org_id, kind=kind)
        return {"status": "disconnected", "kind": kind}

    async def _purge_source_data(self, *, org_id: uuid.UUID, kind: str) -> None:
        params = {"org": str(org_id)}
        if kind == "slack":
            # Cards SET NULL on message delete (won't cascade), so delete them first;
            # messages then cascade their tags + scores.
            for tbl in ("cards", "digests", "insights"):
                await self._s.execute(text(f"DELETE FROM {tbl} WHERE org_id = :org"), params)
            await self._s.execute(
                text("DELETE FROM messages WHERE org_id = :org AND source = 'slack'"),
                params,
            )
            await self._s.execute(
                text("DELETE FROM raw_events WHERE org_id = :org AND source = 'slack'"),
                params,
            )
            await self._s.execute(text("DELETE FROM channels WHERE org_id = :org"), params)
            # Persona members came from Slack (slack_user_id set); the Auth0 admin/real
            # users have it NULL and survive the disconnect.
            await self._s.execute(
                text(
                    "DELETE FROM org_memberships WHERE org_id = :org AND slack_user_id IS NOT NULL",
                ),
                params,
            )
        elif kind == "dropbox":
            # document_chunks cascade on document delete (removes pgvector rows too).
            await self._s.execute(
                text("DELETE FROM documents WHERE org_id = :org AND source = 'dropbox'"),
                params,
            )
            await self._s.execute(
                text("DELETE FROM raw_events WHERE org_id = :org AND source = 'dropbox'"),
                params,
            )
