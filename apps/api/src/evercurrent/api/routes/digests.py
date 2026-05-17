"""Digest routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from evercurrent.api.deps import ArqPool, SessionDep
from evercurrent.api.schemas import DigestResponse, GenerateDigestsResponse
from evercurrent.db.repositories import DigestRepository, ProjectRepository
from evercurrent.digest.generator import generate_digest_for_user

router = APIRouter(prefix="/digests", tags=["digests"])


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
    """Synchronously regenerate one user's digest. Returns the fresh row.

    Used by phase + feedback flows so the user sees the impact of the change
    immediately rather than enqueuing a worker job. ~3-10s of LLM latency.
    """
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
    return DigestResponse.model_validate(digest.model_dump())


@router.get("/{user_id}", response_model=DigestResponse)
async def get_digest(
    user_id: uuid.UUID,
    session: SessionDep,
    day: Annotated[int, Query(ge=1)],
) -> DigestResponse:
    digest = await DigestRepository(session).get(user_id, day)
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="digest not found")
    return DigestResponse.model_validate(digest.model_dump())
