"""Digest routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.api.deps import ArqPool, SessionDep
from evercurrent.api.schemas import DigestItem, DigestResponse, GenerateDigestsResponse
from evercurrent.db.repositories import (
    DigestRepository,
    MessageRepository,
    ProjectRepository,
    UserRepository,
)
from evercurrent.digest.generator import generate_digest_for_user
from evercurrent.domain.digests import Digest as DigestDomain

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
    arq: ArqPool,
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
    project_id: Annotated[uuid.UUID, Query()],
) -> GenerateDigestsResponse:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    job = await arq.enqueue_job("generate_all_digests", str(project_id), day)
    job_id = getattr(job, "job_id", str(uuid.uuid4()))
    return GenerateDigestsResponse(job_id=job_id, day=day)


@router.post("/{user_id}/regenerate", response_model=DigestResponse)
async def regenerate_for_user(
    user_id: uuid.UUID,
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
    project_id: Annotated[uuid.UUID, Query()],
) -> DigestResponse:
    """Synchronously regenerate one user's digest. Returns the fresh row."""
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    content = await generate_digest_for_user(
        project_id=project_id,
        user_id=user_id,
        day=day,
    )
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    digest = await DigestRepository(session).get(user_id, day)
    if digest is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="digest write failed",
        )
    return await _build_response(digest, session)


@router.get("/{user_id}", response_model=DigestResponse)
async def get_digest(
    user_id: uuid.UUID,
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
) -> DigestResponse:
    digest = await DigestRepository(session).get(user_id, day)
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="digest not found")
    return await _build_response(digest, session)
