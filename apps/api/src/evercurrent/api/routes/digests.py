"""Digest routes.

`GET /api/v1/digests/today` — read-through cache. Returns the latest
cached digest for the current member; if it is older than today (the
member's local today), kicks off a regen in the background.

`POST /api/v1/digests/regenerate` — enqueue a forced regen for the
current member + today. Returns the Celery `job_id`. The dashboard
listens on the SSE stream for `digest_ready` to refresh.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.digest import repository as digest_repo
from evercurrent.digest.scheduler import (
    day_index_for_member,
    project_phase_for_member,
)
from evercurrent.jobs.celery_tasks import generate_digest_for_member
from evercurrent.realtime import publish_event

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/digests", tags=["digests"])


class DigestTodayResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    project_member_id: uuid.UUID
    day_index: int
    phase: str
    content_md: str
    card_ids: list[uuid.UUID]
    message_ids: list[uuid.UUID]
    generated_at: str
    is_stale: bool


class RegenerateResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    job_id: str
    project_member_id: uuid.UUID
    day_index: int


@router.get("/today", response_model=DigestTodayResponse)
async def get_today(
    session: SessionDep,
    user: CurrentUserDep,
) -> DigestTodayResponse:
    today_idx = await day_index_for_member(
        session,
        project_member_id=user.membership_id,
        org_id=user.org_id,
    )
    phase = await project_phase_for_member(session, org_id=user.org_id)

    latest = await digest_repo.get_latest_for_member(
        session,
        project_member_id=user.membership_id,
    )
    if latest is None:
        # First-ever read: fire a fresh generate for today and 404. The
        # dashboard will reload via the SSE `digest_ready` event.
        generate_digest_for_member.delay(
            str(user.membership_id),
            today_idx,
            phase,
            force=False,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="digest not yet generated; regen enqueued",
        )

    is_stale = latest.day_index < today_idx
    if is_stale:
        generate_digest_for_member.delay(
            str(user.membership_id),
            today_idx,
            phase,
            force=False,
        )

    return DigestTodayResponse(
        id=latest.id,
        project_member_id=latest.project_member_id,
        day_index=latest.day_index,
        phase=latest.phase,
        content_md=latest.content_md,
        card_ids=latest.card_ids,
        message_ids=latest.message_ids,
        generated_at=latest.generated_at.isoformat(),
        is_stale=is_stale,
    )


@router.post(
    "/regenerate",
    response_model=RegenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate(
    session: SessionDep,
    user: CurrentUserDep,
) -> RegenerateResponse:
    today_idx = await day_index_for_member(
        session,
        project_member_id=user.membership_id,
        org_id=user.org_id,
    )
    phase = await project_phase_for_member(session, org_id=user.org_id)
    result = generate_digest_for_member.delay(
        str(user.membership_id),
        today_idx,
        phase,
        force=True,
    )

    publish_event(
        user.org_id,
        "digest_regen_enqueued",
        {
            "project_member_id": str(user.membership_id),
            "day_index": today_idx,
            "job_id": result.id,
        },
    )

    return RegenerateResponse(
        job_id=result.id,
        project_member_id=user.membership_id,
        day_index=today_idx,
    )
