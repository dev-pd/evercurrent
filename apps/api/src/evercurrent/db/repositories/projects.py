from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Project as ProjectModel


class Project(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    name: Annotated[str, Field(min_length=1, max_length=255)]
    current_phase: Annotated[str, Field(min_length=1, max_length=32)]
    current_day: Annotated[int, Field(ge=1)]
    start_date: dt.date
    phase_concerns: dict[str, list[str]] = Field(default_factory=dict)
    milestones: list[dict[str, str]] = Field(default_factory=list)
    created_at: dt.datetime
    updated_at: dt.datetime

    def date_for_day(self, day: int) -> dt.date:
        return self.start_date + dt.timedelta(days=day - 1)

    @property
    def today_day(self) -> int:
        delta = (dt.datetime.now(dt.UTC).date() - self.start_date).days
        return max(1, delta + 1)


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
        start_date: dt.date | None = None,
        phase_concerns: dict[str, list[str]] | None = None,
        milestones: list[dict[str, str]] | None = None,
    ) -> Project:
        values: dict[str, object] = {
            "name": name,
            "current_phase": current_phase,
            "current_day": current_day,
            "phase_concerns": phase_concerns or {},
            "milestones": milestones or [],
        }
        if start_date is not None:
            values["start_date"] = start_date
        stmt = (
            pg_insert(ProjectModel)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[ProjectModel.name],
                set_={k: v for k, v in values.items() if k != "name"},
            )
            .returning(ProjectModel)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one()
        return Project.model_validate(row)

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        name: str,
        current_phase: str,
        start_date: dt.date,
        current_day: int = 1,
        phase_concerns: dict[str, list[str]] | None = None,
    ) -> Project:
        row = ProjectModel(
            org_id=org_id,
            name=name,
            current_phase=current_phase,
            current_day=current_day,
            start_date=start_date,
            phase_concerns=phase_concerns or {},
            milestones=[],
        )
        self._s.add(row)
        await self._s.flush()
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
