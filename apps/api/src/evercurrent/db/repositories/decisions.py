"""Decision repository."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Decision as DecisionModel
from evercurrent.domain.decisions import Decision, DecisionStatus


class DecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, decision_id: uuid.UUID) -> Decision | None:
        row = await self._s.get(DecisionModel, decision_id)
        return Decision.model_validate(row) if row else None

    async def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        since: dt.datetime | None = None,
        status: DecisionStatus | None = None,
        limit: int = 100,
    ) -> list[Decision]:
        stmt = select(DecisionModel).where(DecisionModel.project_id == project_id)
        if since:
            stmt = stmt.where(DecisionModel.decided_at >= since)
        if status:
            stmt = stmt.where(DecisionModel.status == status.value)
        stmt = stmt.order_by(DecisionModel.decided_at.desc()).limit(limit)
        result = await self._s.execute(stmt)
        return [Decision.model_validate(r) for r in result.scalars()]

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        summary: str,
        decided_by: str,
        decided_at: dt.datetime,
        status: DecisionStatus,
        confidence: float,
        rationale: str | None = None,
        source_message_ids: list[uuid.UUID] | None = None,
        affected_subsystems: list[str] | None = None,
    ) -> Decision:
        row = DecisionModel(
            project_id=project_id,
            summary=summary,
            rationale=rationale,
            decided_by=decided_by,
            decided_at=decided_at,
            source_message_ids=source_message_ids or [],
            affected_subsystems=affected_subsystems or [],
            status=status.value,
            confidence=confidence,
        )
        self._s.add(row)
        await self._s.flush()
        await self._s.refresh(row)
        return Decision.model_validate(row)
