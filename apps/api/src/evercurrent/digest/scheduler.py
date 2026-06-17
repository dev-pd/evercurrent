"""Decides whose digest is due: maps each member's local digest hour + timezone
to a day index and enqueues generation for members due in the current window."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import get_settings
from evercurrent.db.session import session_scope
from evercurrent.digest import repository as digest_repo

if TYPE_CHECKING:
    from collections.abc import Callable

log = structlog.get_logger(__name__)


def _safe_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        log.warning("digest.scheduler.bad_tz", tz=tz_name)
        return ZoneInfo("UTC")


def members_due_at(
    now_utc: dt.datetime,
    memberships: list[dict[str, object]],
) -> list[uuid.UUID]:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=dt.UTC)

    settings = get_settings()
    due: list[uuid.UUID] = []
    for m in memberships:
        tz_name = str(m.get("timezone") or "UTC")
        local = now_utc.astimezone(_safe_zone(tz_name))
        if local.hour == settings.digest_hour and local.minute < settings.digest_window_minutes:
            due.append(uuid.UUID(str(m["id"])))
    return due


async def day_index_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    org_id: uuid.UUID,
    now_utc: dt.datetime | None = None,
) -> int:
    if now_utc is None:
        now_utc = dt.datetime.now(dt.UTC)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=dt.UTC)

    tz_row = (
        await session.execute(
            text("SELECT timezone FROM org_memberships WHERE id = :id"),
            {"id": str(project_member_id)},
        )
    ).first()
    tz_name = str(tz_row[0]) if tz_row and tz_row[0] else "UTC"
    local_today = now_utc.astimezone(_safe_zone(tz_name)).date()

    proj_row = (
        await session.execute(
            text(
                "SELECT start_date FROM projects WHERE org_id = :oid "
                "ORDER BY created_at DESC LIMIT 1",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if proj_row is None or proj_row[0] is None:
        return 0
    start_date: dt.date = proj_row[0]
    return max(0, (local_today - start_date).days)


async def project_phase_for_member(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
) -> str:
    row = (
        await session.execute(
            text(
                "SELECT current_phase FROM projects WHERE org_id = :oid "
                "ORDER BY created_at DESC LIMIT 1",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if row is None or row[0] is None:
        return "DVT"
    return str(row[0])


async def enqueue_due_digests_now(
    *,
    enqueuer: Callable[[str, int, str], object] | None = None,
    now_utc: dt.datetime | None = None,
) -> list[dict[str, object]]:
    if now_utc is None:
        now_utc = dt.datetime.now(dt.UTC)

    if enqueuer is None:
        from evercurrent.jobs.celery_tasks import (  # noqa: PLC0415  break circular import
            generate_digest_for_member,
        )

        def _default_enqueue(mid: str, day_index: int, phase: str) -> object:
            return generate_digest_for_member.delay(
                mid,
                day_index,
                phase,
                force=False,
            )

        enqueuer = _default_enqueue

    async with session_scope() as session:
        memberships = await digest_repo.list_active_memberships(session)
        due_ids = members_due_at(now_utc, memberships)

        enqueued: list[dict[str, object]] = []
        for mid in due_ids:
            mem_row = next(
                (m for m in memberships if uuid.UUID(str(m["id"])) == mid),
                None,
            )
            if mem_row is None:
                continue
            org_id = uuid.UUID(str(mem_row["org_id"]))
            day_index = await day_index_for_member(
                session,
                project_member_id=mid,
                org_id=org_id,
                now_utc=now_utc,
            )
            phase = await project_phase_for_member(session, org_id=org_id)
            enqueuer(str(mid), day_index, phase)
            enqueued.append(
                {
                    "membership_id": str(mid),
                    "day_index": day_index,
                    "phase": phase,
                },
            )

        log.info(
            "digest.scheduler.scan",
            now_utc=now_utc.isoformat(),
            membership_count=len(memberships),
            due_count=len(due_ids),
        )
        return enqueued
