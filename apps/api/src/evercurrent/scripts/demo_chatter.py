"""Demo chatter script: post a few fresh persona messages to Slack on demand.

    python -m evercurrent.scripts.demo_chatter

Generates persona chatter (Sonnet), posts it via the demo bot token, and lets
the real webhook -> route_message pipeline ingest it. Use to seed live activity
during a demo. Not a scheduled task — run it when you want a fresh batch.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.llm.tiering import ModelTier
from evercurrent.scripts.personas import BY_NAME
from evercurrent.scripts.synthetic import CHANNEL_TOPICS, generate_batch
from evercurrent.scripts.synthetic_schemas import PHASES

log = structlog.get_logger(__name__)


def _phase_for(key: str) -> Any:
    for p in PHASES:
        if p.key == key.lower():
            return p
    return PHASES[1]


async def emit_chatter() -> dict[str, Any]:
    settings = get_settings()
    token = settings.slack_demo_bot_token
    if not token:
        return {"status": "no_token"}

    channels = list(CHANNEL_TOPICS)
    phase = _phase_for(settings.demo_chatter_phase)
    # Total bot messages to post (BOT_MSGS_COUNT env, else the config default),
    # spread across channels so signals span subsystems — not one channel.
    count = int(os.environ.get("BOT_MSGS_COUNT", str(settings.demo_chatter_batch)))

    client = SlackClient(bot_token=token)
    posted = 0
    used: list[str] = []
    try:
        live = await client.list_all_channels()
        name_to_id = {c.name: c.id for c in live}
        targets = [name for name in channels if name in name_to_id]
        if not targets:
            return {"status": "no_channels"}

        per_channel = max(1, count // len(targets))
        for name in targets:
            remaining = count - posted
            if remaining <= 0:
                break
            want = min(per_channel, remaining)
            msgs = await generate_batch(
                channel=name,
                phase=phase,
                count=want,
                threads=1,
                tier=ModelTier.DIGEST,
            )
            channel_posted = 0
            for m in msgs[:want]:
                persona = BY_NAME.get(m.author)
                try:
                    await client.chat_post_message(
                        channel=name_to_id[name],
                        text=m.text,
                        username=m.author,
                        icon_emoji=persona.emoji if persona else None,
                    )
                    posted += 1
                    channel_posted += 1
                except SlackAPIError as exc:
                    log.warning("demo_chatter.post_failed", author=m.author, error=exc.error)
            if channel_posted:
                used.append(name)
    finally:
        await client.aclose()
    log.info("demo_chatter.emitted", channels=used, phase=phase.key, posted=posted)
    return {"status": "ok", "channels": used, "posted": posted}


async def main() -> None:
    print(await emit_chatter())


if __name__ == "__main__":
    asyncio.run(main())
