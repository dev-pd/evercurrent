from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from evercurrent.api.schemas import DocumentResponse
from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.db.repositories import DocumentRepository, ProjectRepository

router = APIRouter(prefix="/documents", tags=["documents"])

_EXCERPT_CHARS = 280


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    session: SessionDep,
    user: CurrentUserDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    phase: Annotated[str | None, Query()] = None,
) -> list[DocumentResponse]:
    _ = user
    if project_id is None:
        projects = await ProjectRepository(session).list_all()
        if not projects:
            return []
        project_id = projects[0].id
    docs = await DocumentRepository(session).list_for_project(project_id)
    out: list[DocumentResponse] = []
    for d in docs:
        if phase and d.phases and phase not in d.phases:
            continue
        excerpt = d.body[:_EXCERPT_CHARS]
        if len(d.body) > _EXCERPT_CHARS:
            excerpt += "…"
        out.append(
            DocumentResponse(
                id=d.id,
                project_id=d.project_id,
                kind=d.kind.value,
                title=d.title,
                phases=d.phases,
                body_excerpt=excerpt,
                chars=len(d.body),
            ),
        )
    return out
