"""SQL for Eve's insights: persist a generated insight and read them back
(paginated) for the insights API."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class InsightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def recent_title_summaries(
        self,
        *,
        org_id: uuid.UUID,
        limit: int = 8,
    ) -> list[tuple[str | None, str | None]]:
        rows = (
            await self._s.execute(
                text(
                    "SELECT payload->>'title', payload->>'summary' FROM insights "
                    "WHERE org_id = :o ORDER BY created_at DESC LIMIT :n",
                ),
                {"o": str(org_id), "n": limit},
            )
        ).all()
        return [(r[0], r[1]) for r in rows]

    async def count_since_day_start(self, *, org_id: uuid.UUID) -> int:
        return (
            await self._s.execute(
                text(
                    "SELECT count(*) FROM insights WHERE org_id = :o "
                    "AND created_at >= date_trunc('day', now())",
                ),
                {"o": str(org_id)},
            )
        ).scalar_one()

    async def insert_payload(self, *, org_id: uuid.UUID, payload: dict[str, Any]) -> None:
        await self._s.execute(
            text("INSERT INTO insights (org_id, payload) VALUES (:org, CAST(:p AS jsonb))"),
            {"org": str(org_id), "p": json.dumps(payload)},
        )

    async def list_payloads(self, *, org_id: uuid.UUID, limit: int) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                text(
                    "SELECT payload FROM insights WHERE org_id = :org "
                    "ORDER BY created_at DESC LIMIT :n",
                ),
                {"org": str(org_id), "n": limit},
            )
        ).all()
        return [row[0] for row in rows]

    async def get_first_project_id(self) -> uuid.UUID | None:
        row = (await self._s.execute(text("SELECT id FROM projects LIMIT 1"))).first()
        if row is None:
            return None
        return uuid.UUID(str(row[0]))
