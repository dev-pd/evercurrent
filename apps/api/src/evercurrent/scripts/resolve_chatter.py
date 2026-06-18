"""Simulation step 2: post follow-up + resolving replies into existing threads.

    python -m evercurrent.scripts.resolve_chatter

Run AFTER seeding chatter (make demo-chatter / make webhook) so open signals
exist. Finds open signals, posts a clearly-resolving reply into a few of their
threads — which the webhook -> route_message -> Haiku resolve-check then closes,
emitting `signal_resolved` live — and a non-resolving "still working on it"
reply into a few others (live activity without resolution). Drives the
real-time demo: boards update in place, the blocker board drops resolved risks,
and the digest staleness banner appears. Not a scheduled task.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog
from sqlalchemy import text

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.db.session import admin_session_scope
from evercurrent.scripts.personas import PERSONAS

log = structlog.get_logger(__name__)


def resolving_text(kind: str, summary: str) -> str:
    if kind == "risk":
        return (
            f"This is now RESOLVED — no further action needed. The risk "
            f"'{summary}' has been fully mitigated: the fix is implemented, "
            "verified in test, and signed off. Removing it from the open-risk "
            "register and closing this thread."
        )
    if kind == "question":
        return (
            f"This is now RESOLVED — no further action needed. The open question "
            f"'{summary}' is definitively answered and agreed by all owners. "
            "Closing this thread."
        )
    return (
        f"This is now RESOLVED — no further action needed. The decision on "
        f"'{summary}' is final: reviewed, approved, and signed off by all "
        "owners. Locking it in and closing this thread."
    )


def context_text(summary: str) -> str:
    return (
        f"Quick follow-up on '{summary}' — still working through it, "
        "more data coming. Not resolved yet."
    )


async def _open_signals() -> list[dict[str, Any]]:
    async with admin_session_scope() as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT s.id, s.kind, s.summary, m.channel, m.external_id "
                        "FROM signals s "
                        "JOIN messages m ON m.id = s.triggering_message_id "
                        "WHERE s.status = 'open' AND m.channel IS NOT NULL "
                        "  AND m.external_id IS NOT NULL "
                        "ORDER BY s.created_at DESC",
                    ),
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


async def _post_reply(
    client: SlackClient,
    sig: dict[str, Any],
    *,
    body: str,
    persona_index: int,
    failure_event: str,
) -> bool:
    persona = PERSONAS[persona_index % len(PERSONAS)]
    try:
        await client.chat_post_message(
            channel=str(sig["channel"]),
            text=body,
            username=persona.name,
            icon_emoji=persona.emoji,
            thread_ts=str(sig["external_id"]),
        )
    except SlackAPIError as exc:
        log.warning(failure_event, signal_id=str(sig["id"]), error=exc.error)
        return False
    return True


async def emit_updates(*, resolve_count: int, context_count: int) -> dict[str, Any]:
    settings = get_settings()
    token = settings.slack_demo_bot_token
    if not token:
        return {"status": "no_token"}

    signals = await _open_signals()
    if not signals:
        return {"status": "no_open_signals"}

    to_resolve = signals[:resolve_count]
    to_context = signals[resolve_count : resolve_count + context_count]

    client = SlackClient(bot_token=token)
    resolving = 0
    context = 0
    try:
        for i, sig in enumerate(to_resolve):
            body = resolving_text(str(sig["kind"]), str(sig["summary"]))
            if await _post_reply(
                client,
                sig,
                body=body,
                persona_index=i,
                failure_event="resolve_chatter.resolve_post_failed",
            ):
                resolving += 1
        for i, sig in enumerate(to_context):
            body = context_text(str(sig["summary"]))
            if await _post_reply(
                client,
                sig,
                body=body,
                persona_index=i + len(to_resolve),
                failure_event="resolve_chatter.context_post_failed",
            ):
                context += 1
    finally:
        await client.aclose()

    result = {
        "status": "ok",
        "resolving": resolving,
        "context": context,
        "open_signals": len(signals),
    }
    log.info("resolve_chatter.emitted", **result)
    return result


async def main() -> None:
    resolve_count = int(os.environ.get("SIM_RESOLVE_COUNT", "2"))
    context_count = int(os.environ.get("SIM_CONTEXT_COUNT", "2"))
    print(await emit_updates(resolve_count=resolve_count, context_count=context_count))


if __name__ == "__main__":
    asyncio.run(main())
