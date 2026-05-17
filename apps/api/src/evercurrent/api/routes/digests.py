"""Digest routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.api.deps import SessionDep
from evercurrent.api.schemas import DigestItem, DigestResponse, GenerateDigestsResponse
from evercurrent.db.repositories import (
    DigestRepository,
    MessageRepository,
    ProjectRepository,
    UserRepository,
)
from evercurrent.domain.digests import Digest as DigestDomain
from evercurrent.jobs.celery_tasks import (
    generate_all_digests as celery_generate_all_digests,
)
from evercurrent.jobs.celery_tasks import (
    regenerate_user_digest as celery_regenerate_user_digest,
)

router = APIRouter(prefix="/digests", tags=["digests"])


async def _build_response(digest: DigestDomain, session: AsyncSession) -> DigestResponse:
    """Hydrate item_message_ids with channel + author + text + tag."""
    msgs = MessageRepository(session)
    users = UserRepository(session)
    items: list[DigestItem] = []
    for mid in digest.item_message_ids:
        enriched = await msgs.get_enriched(mid)
        if enriched is None:
            continue
        author = await users.get_by_id(enriched.message.author_id)
        items.append(
            DigestItem(
                id=enriched.message.id,
                channel=enriched.channel_name,
                author_username=enriched.author_username,
                author_display_name=author.display_name if author else enriched.author_username,
                day=enriched.message.day,
                ts=enriched.message.ts,
                text=enriched.message.text,
                topic=enriched.tag.topic if enriched.tag else None,
                urgency=enriched.tag.urgency.value if enriched.tag else None,
            ),
        )
    return DigestResponse(
        id=digest.id,
        user_id=digest.user_id,
        day=digest.day,
        phase=digest.phase,
        content_md=digest.content_md,
        item_message_ids=digest.item_message_ids,
        items=items,
        generated_at=digest.generated_at,
    )


@router.post(
    "/generate",
    response_model=GenerateDigestsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate(
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
    project_id: Annotated[uuid.UUID, Query()],
) -> GenerateDigestsResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    result = celery_generate_all_digests.delay(str(project_id), day)
    return GenerateDigestsResponse(job_id=result.id, day=day)


@router.post(
    "/{user_id}/regenerate",
    response_model=GenerateDigestsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_for_user(
    user_id: uuid.UUID,
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
    project_id: Annotated[uuid.UUID, Query()],
) -> GenerateDigestsResponse:
    """Enqueue a per-user regenerate task onto Celery.

    Each call produces a fresh task_id — Celery doesn't dedup against
    completed results, so re-clicks always re-run.
    """
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    result = celery_regenerate_user_digest.delay(
        str(project_id),
        str(user_id),
        day,
        project.current_phase,
    )
    return GenerateDigestsResponse(job_id=result.id, day=day)


@router.get("/{user_id}", response_model=DigestResponse)
async def get_digest(
    user_id: uuid.UUID,
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> DigestResponse:
    """Return the precomputed digest for (user, day, project.current_phase)."""
    repo = DigestRepository(session)
    phase: str | None = None
    if project_id is not None:
        project = await ProjectRepository(session).get_by_id(project_id)
        if project is not None:
            phase = project.current_phase
    digest = await repo.get(user_id, day, phase=phase)
    if digest is None and phase is not None:
        digest = await repo.get(user_id, day)
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="digest not found")
    return await _build_response(digest, session)
