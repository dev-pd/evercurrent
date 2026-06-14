"""Live demo chatter: periodically post a few fresh persona messages to Slack.

Gated behind settings.demo_chatter_enabled. Generates with the DIGEST tier
(Sonnet) for quality on low volume, posts via the demo bot token, and lets the
real webhook -> route_message pipeline ingest them. Mimics a live team.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import structlog

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.ingestion.personas import BY_NAME
from evercurrent.ingestion.synthetic import CHANNEL_TOPICS, generate_batch
from evercurrent.ingestion.synthetic_schemas import PHASES
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)


def _phase_for(key: str) -> Any:
    for p in PHASES:
        if p.key == key.lower():
            return p
    return PHASES[1]


async def emit_chatter(_ctx: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.demo_chatter_enabled:
        return {"status": "disabled"}
    token = settings.slack_demo_bot_token
    if not token:
        return {"status": "no_token"}

    channels = list(CHANNEL_TOPICS)
    channel = channels[dt.datetime.now(dt.UTC).minute % len(channels)]
    phase = _phase_for(settings.demo_chatter_phase)

    client = SlackClient(bot_token=token)
    posted = 0
    try:
        live = await client.list_all_channels()
        cid = next((c.id for c in live if c.name == channel), None)
        if cid is None:
            return {"status": "channel_missing", "channel": channel}
        msgs = await generate_batch(
            channel=channel, phase=phase, count=settings.demo_chatter_batch,
            threads=1, tier=ModelTier.DIGEST,
        )
        for m in msgs:
            persona = BY_NAME.get(m.author)
            try:
                await client.chat_post_message(
                    channel=cid, text=m.text, username=m.author,
                    icon_emoji=persona.emoji if persona else None,
                )
                posted += 1
            except SlackAPIError as exc:
                log.warning("demo_chatter.post_failed", author=m.author, error=exc.error)
    finally:
        await client.aclose()
    log.info("demo_chatter.emitted", channel=channel, phase=phase.key, posted=posted)
    return {"status": "ok", "channel": channel, "posted": posted}
