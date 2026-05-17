"""Arq task: refresh today's digests.

Today = `project.current_day`. The cron fires every 2 minutes and:
1. Tags every new (untagged) message that landed since the last run.
2. Regenerates digests for every user under the project's current phase
   so the dashboard is never more than 2 min behind reality.
3. Re-extracts decisions for the day.

Idempotent — tag upserts skip already-tagged messages; digest upserts
overwrite the matching (user, day, phase) row.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


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

    day = project.current_day
    phase = project.current_phase

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


async def synthesize_today_message(  # noqa: PLR0911
    _ctx: dict[str, Any],
    project_name: str | None = None,
) -> dict[str, Any]:
    """Generate one new message in the today bucket via Sonnet.

    Picks a recent thread context, asks the model to extend the narrative
    with one realistic Slack-style message, persists it as part of
    `current_day`. Skipped silently when ANTHROPIC_API_KEY is unset.
    """
    import json
    import os

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
        # Use the last day of seed data as context, plus anything already
        # in today's bucket.
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
        for em in prior[-10:] + today[-10:]
    ]

    prompt = (
        "You write one realistic Slack message that extends an ongoing\n"
        "hardware-engineering project narrative for the warehouse robot v2.\n"
        "Pick exactly one of the listed channels and one of the listed\n"
        "usernames as the author. The message should be technical, short\n"
        "(1-3 sentences), and reference part numbers / topics already seen\n"
        "in the context. Reply with a JSON object only.\n\n"
        f"Channels: {[c.name for c in channels]}\n"
        f"Usernames: {[u.username for u in users]}\n\n"
        f"Recent context (newest last):\n{json.dumps(context, indent=2)}\n\n"
        'Output schema: {"channel": str, "author_username": str, "text": str}.\n'
    )
    provider = get_provider()
    raw = await provider.complete_json(
        tier=ModelTier.DIGEST,
        system="You produce JSON-only output. No prose.",
        prompt=prompt,
        max_tokens=512,
        temperature=0.6,
    )
    if not isinstance(raw, dict):
        return {"status": "bad_output"}
    channel_name = str(raw.get("channel", "")).strip()
    author_username = str(raw.get("author_username", "")).strip()
    text = str(raw.get("text", "")).strip()
    if not channel_name or not author_username or not text:
        return {"status": "missing_fields"}

    user_by_username = {u.username: u for u in users}
    channel_by_name = {c.name: c for c in channels}
    user = user_by_username.get(author_username)
    channel = channel_by_name.get(channel_name)
    if user is None or channel is None:
        return {"status": "unknown_channel_or_user"}

    async with session_scope() as session:
        msgs = MessageRepository(session)
        created = await msgs.create(
            project_id=project.id,
            channel_id=channel.id,
            author_id=user.id,
            day=project.current_day,
            text=text,
            ts=dt.datetime.now(dt.UTC),
            reactions={},
        )
        await session.commit()
    log.info(
        "synthesize_today_message.done",
        project_id=str(project.id),
        message_id=str(created.id),
        author=author_username,
        channel=channel_name,
    )
    return {
        "status": "ok",
        "message_id": str(created.id),
        "channel": channel_name,
        "author": author_username,
    }


def _new_message_uuid() -> uuid.UUID:
    return uuid.uuid4()
