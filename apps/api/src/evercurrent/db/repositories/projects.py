"""Project repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Project as ProjectModel
from evercurrent.domain.projects import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        row = await self._s.get(ProjectModel, project_id)
        return Project.model_validate(row) if row else None

    async def get_by_name(self, name: str) -> Project | None:
        result = await self._s.execute(select(ProjectModel).where(ProjectModel.name == name))
        row = result.scalar_one_or_none()
        return Project.model_validate(row) if row else None

    async def list_all(self) -> list[Project]:
        result = await self._s.execute(select(ProjectModel).order_by(ProjectModel.name))
        return [Project.model_validate(r) for r in result.scalars()]

    async def upsert(
        self,
        *,
        name: str,
        current_phase: str,
        current_day: int = 1,
        phase_concerns: dict[str, list[str]] | None = None,
        milestones: list[dict[str, str]] | None = None,
    ) -> Project:
        stmt = (
            pg_insert(ProjectModel)
            .values(
                name=name,
                current_phase=current_phase,
                current_day=current_day,
                phase_concerns=phase_concerns or {},
                milestones=milestones or [],
            )
            .on_conflict_do_update(
                index_elements=[ProjectModel.name],
                set_={
                    "current_phase": current_phase,
                    "current_day": current_day,
                    "phase_concerns": phase_concerns or {},
                    "milestones": milestones or [],
                },
            )
            .returning(ProjectModel)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one()
        return Project.model_validate(row)

    async def set_phase(self, project_id: uuid.UUID, phase: str) -> Project | None:
        row = await self._s.get(ProjectModel, project_id)
        if row is None:
            return None
        row.current_phase = phase
        await self._s.flush()
        # Server-side onupdate=func.now() leaves `updated_at` in an expired
        # state; refresh so Pydantic from_attributes can read it without a
        # lazy-load (which fails after the session greenlet has unwound).
        await self._s.refresh(row)
        return Project.model_validate(row)

    async def set_current_day(self, project_id: uuid.UUID, day: int) -> Project | None:
        row = await self._s.get(ProjectModel, project_id)
        if row is None:
            return None
        row.current_day = day
        await self._s.flush()
        await self._s.refresh(row)
        return Project.model_validate(row)
