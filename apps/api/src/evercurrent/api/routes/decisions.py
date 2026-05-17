"""Decision routes."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from evercurrent.api.deps import SessionDep
from evercurrent.api.schemas import DecisionResponse
from evercurrent.db.repositories import DecisionRepository, ProjectRepository
from evercurrent.domain.decisions import DecisionStatus

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("", response_model=list[DecisionResponse])
async def list_decisions(
    session: SessionDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    since: Annotated[dt.datetime | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[DecisionResponse]:
    if project_id is None:
        projects = await ProjectRepository(session).list_all()
        if not projects:
            return []
        project_id = projects[0].id
    status_enum: DecisionStatus | None = None
    if status:
        try:
            status_enum = DecisionStatus(status)
        except ValueError:
            return []
    decisions = await DecisionRepository(session).list_for_project(
        project_id,
        since=since,
        status=status_enum,
        limit=limit,
    )
    return [DecisionResponse.model_validate(d.model_dump()) for d in decisions]
