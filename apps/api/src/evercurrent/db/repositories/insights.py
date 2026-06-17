"""SQL for Eve's insights: persist a generated insight and read them back
(paginated) for the insights API."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class InsightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

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
