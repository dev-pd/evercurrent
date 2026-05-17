"""Cron tasks that simulate the live Slack stream.

`refresh_today` — runs every 30s. It rolls `project.current_day`
forward to wall-clock today, enriches any newly-arrived messages, and
regenerates digests for the current phase x every user. Idempotent.

`synthesize_today_message` — runs every 60s. It asks Sonnet for a
small batch of realistic Slack messages that extend the project
narrative on today's date, scoped to the current project phase.

Production: replace synthesize with a Slack webhook listener that
enqueues `enrich + nudge_refresh` per inbound message; the 30s cron
stays as a backstop.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_SYNTHESIZE_BATCH = 2


async def _roll_day_if_needed(project_id: str) -> tuple[int, str]:
    from evercurrent.db.repositories import ProjectRepository
    from evercurrent.db.session import session_scope

    async with session_scope() as session:
        repo = ProjectRepository(session)
        project = await repo.get_by_id(uuid.UUID(project_id))
        if project is None:
            msg = f"project {project_id} not found"
            raise LookupError(msg)
        expected = project.today_day
        if project.current_day == expected:
            return project.current_day, project.current_phase
        updated = await repo.set_current_day(project.id, expected)
        await session.commit()
        log.info(
            "refresh_today.rollover",
            project_id=project_id,
            from_day=project.current_day,
            to_day=expected,
        )
        if updated is not None:
            return updated.current_day, updated.current_phase
        return expected, project.current_phase


async def refresh_today(_ctx: dict[str, Any], project_name: str | None = None) -> dict[str, Any]:
    from evercurrent.db.repositories import ProjectRepository
    from evercurrent.db.session import session_scope
    from evercurrent.decisions.extractor import extract_decisions_for_day
    from evercurrent.digest.generator import generate_all_digests_for_day
    from evercurrent.jobs.tasks.enrich_messages import enrich_day

    target = project_name or "Warehouse Robot v2"
    async with session_scope() as session:
        project = await ProjectRepository(session).get_by_name(target)
    if project is None:
        log.warning("refresh_today.skip_missing_project", name=target)
        return {"status": "no_project"}

    day, phase = await _roll_day_if_needed(str(project.id))

    enrich = await enrich_day({}, str(project.id), day)
    digests = await generate_all_digests_for_day(project.id, day, phase=phase)
    decisions = await extract_decisions_for_day(project.id, day)

    payload = {
        "project_id": str(project.id),
        "day": day,
        "phase": phase,
        "tagged": enrich.get("tagged", 0),
        "digests_written": digests,
        "decisions_written": decisions,
        "completed_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    log.info("refresh_today.done", **payload)
    return payload


async def synthesize_today_message(
    _ctx: dict[str, Any],
    project_name: str | None = None,
) -> dict[str, Any]:
    from evercurrent.db.repositories import (
        ChannelRepository,
        MessageRepository,
        ProjectRepository,
        UserRepository,
    )
    from evercurrent.db.session import session_scope
    from evercurrent.llm.client import get_provider
    from evercurrent.llm.tiering import ModelTier

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"status": "no_key"}

    target = project_name or "Warehouse Robot v2"
    async with session_scope() as session:
        project = await ProjectRepository(session).get_by_name(target)
        if project is None:
            return {"status": "no_project"}
        users = await UserRepository(session).list_for_project(project.id)
        channels = await ChannelRepository(session).list_for_project(project.id)
        msgs_repo = MessageRepository(session)
        prior_day = max(1, project.current_day - 1)
        prior = await msgs_repo.list_for_day(project.id, prior_day, with_tags=True)
        today = await msgs_repo.list_for_day(project.id, project.current_day, with_tags=True)

    if not users or not channels:
        return {"status": "no_users_or_channels"}

    context = [
        {
            "channel": em.channel_name,
            "author": em.author_username,
            "ts": em.message.ts.isoformat(),
            "text": em.message.text,
        }
        for em in prior[-8:] + today[-8:]
    ]

    phase = project.current_phase
    phase_concerns = project.phase_concerns.get(phase, [])

    prompt = (
        "You generate realistic Slack messages for a hardware engineering\n"
        f"team currently in the {phase} phase of project '{project.name}'.\n"
        f"Phase concerns for {phase}: {phase_concerns}\n\n"
        f"Produce a JSON array of EXACTLY {_SYNTHESIZE_BATCH} message objects\n"
        "that extend the narrative. Each message must:\n"
        f"- Pick channel from: {[c.name for c in channels]}\n"
        f"- Pick author_username from: {[u.username for u in users]}\n"
        "- Reference part numbers / topics already in the context\n"
        f"- Stay relevant to a {phase} engineer's concerns (above)\n"
        "- Be 1-3 sentences, technical, no fluff\n\n"
        "Use diverse authors + channels across the batch (don't repeat).\n\n"
        f"Recent context (newest last):\n{json.dumps(context, indent=2)}\n\n"
        'Output schema: [{"channel": str, "author_username": str, "text": str}, ...]\n'
    )
    provider = get_provider()
    raw = await provider.complete_json(
        tier=ModelTier.DIGEST,
        system="You produce JSON-only output. No prose.",
        prompt=prompt,
        max_tokens=1024,
        temperature=0.7,
    )
    if not isinstance(raw, list):
        return {"status": "bad_output"}

    user_by_username = {u.username: u for u in users}
    channel_by_name = {c.name: c for c in channels}
    inserted: list[dict[str, str]] = []

    async with session_scope() as session:
        msgs = MessageRepository(session)
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            channel_name = str(entry.get("channel", "")).strip()
            author_username = str(entry.get("author_username", "")).strip()
            text = str(entry.get("text", "")).strip()
            if not channel_name or not author_username or not text:
                continue
            user = user_by_username.get(author_username)
            channel = channel_by_name.get(channel_name)
            if user is None or channel is None:
                continue
            created = await msgs.create(
                project_id=project.id,
                channel_id=channel.id,
                author_id=user.id,
                day=project.current_day,
                text=text,
                ts=dt.datetime.now(dt.UTC),
                reactions={},
            )
            inserted.append(
                {
                    "message_id": str(created.id),
                    "channel": channel_name,
                    "author": author_username,
                },
            )
        await session.commit()
    log.info(
        "synthesize_today_message.done",
        project_id=str(project.id),
        count=len(inserted),
        phase=phase,
        day=project.current_day,
    )
    return {"status": "ok", "count": len(inserted), "messages": inserted}
