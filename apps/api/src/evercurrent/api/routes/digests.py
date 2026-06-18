"""Routes for the per-member digest: fetch today's digest and trigger regeneration."""

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
from evercurrent.sse_publisher import publish_event

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/digests", tags=["digests"])

# New scored messages since generation needed before a digest reads as stale.
_NEW_ACTIVITY_THRESHOLD = 3


def _compute_is_stale(
    *,
    day_index: int,
    today_index: int,
    resolved_cited: int,
    new_messages: int,
    new_threshold: int,
) -> bool:
    """A digest is stale if it's from a past day, a signal it cited has closed,
    or enough new activity has landed to be worth a refresh. No LLM — pure SQL
    counts drive a banner; the user regenerates on demand."""
    return (
        day_index < today_index
        or resolved_cited > 0
        or new_messages >= new_threshold
    )


class DigestItemV2(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    bucket: str
    source: str
    author_display_name: str | None = None
    ts: str | None = None
    why_this_matters: str
    signal_id: uuid.UUID | None = None


class DigestTodayResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    project_member_id: uuid.UUID
    day_index: int
    phase: str
    content_md: str
    items: list[DigestItemV2]
    signal_ids: list[uuid.UUID]
    message_ids: list[uuid.UUID]
    generated_at: str
    is_stale: bool
    stale_resolved_signals: int
    stale_new_messages: int


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

    resolved_cited = await digest_repo.count_resolved_cited_signals(
        session,
        signal_ids=latest.signal_ids,
    )
    new_messages = await digest_repo.count_new_scored_since(
        session,
        project_member_id=user.membership_id,
        since=latest.generated_at,
    )
    is_stale = _compute_is_stale(
        day_index=latest.day_index,
        today_index=today_idx,
        resolved_cited=resolved_cited,
        new_messages=new_messages,
        new_threshold=_NEW_ACTIVITY_THRESHOLD,
    )

    items = await _build_items(
        session,
        message_ids=latest.message_ids,
    )

    return DigestTodayResponse(
        id=latest.id,
        project_member_id=latest.project_member_id,
        day_index=latest.day_index,
        phase=latest.phase,
        content_md=latest.content_md,
        items=items,
        signal_ids=latest.signal_ids,
        message_ids=latest.message_ids,
        generated_at=latest.generated_at.isoformat(),
        is_stale=is_stale,
        stale_resolved_signals=resolved_cited,
        stale_new_messages=new_messages,
    )


async def _build_items(
    session,  # noqa: ANN001
    *,
    message_ids: list[uuid.UUID],
) -> list[DigestItemV2]:
    rows = await digest_repo.load_message_items(session, message_ids=message_ids)
    out: list[DigestItemV2] = []
    for r in rows:
        urgency = (r.urgency or "normal").lower()
        bucket = (
            "top_priority" if urgency == "high" else "watch_outs" if urgency == "normal" else "fyi"
        )
        out.append(
            DigestItemV2(
                id=str(r.id),
                bucket=bucket,
                source=f"#{r.channel}" if r.channel else "—",
                author_display_name=r.author_display_name,
                ts=r.posted_at.isoformat() if r.posted_at else None,
                why_this_matters=(r.text or "")[:280],
                signal_id=None,
            ),
        )
    top = [i for i in out if i.bucket == "top_priority"][:8]
    watch = [i for i in out if i.bucket == "watch_outs"][:8]
    fyi = [i for i in out if i.bucket == "fyi"][:6]
    return top + watch + fyi


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
