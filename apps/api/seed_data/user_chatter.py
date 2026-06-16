"""Post LLM-generated messages to Slack as a real user (xoxp- token) so the
live webhook ingests them.

The demo bot can't drive the webhook: Slack suppresses an app's own bot
messages and the handler skips `bot_message` subtypes. A user-token post is a
normal user message (no subtype, distinct identity) so Slack delivers it to the
Events API -> /webhooks/slack -> route_message.

Message text comes from the same `generate_batch` (Haiku) the personas use, so
it's channel/phase-aware and rich enough that the tagger extracts entities
(which generic canned text did not -> subsystem scoring stayed at 0).

Env: SLACK_USER_TOKEN (xoxp-..., chat:write), ANTHROPIC_API_KEY. Optional
CHATTER_CHANNEL (channel name, default mech-design), CHATTER_COUNT (per run),
CHATTER_INTERVAL (seconds between posts), CHATTER_PHASE (default fcs).

Run one message:   make webhook-chatter
Burst:             make webhook-chatter COUNT=5 INTERVAL=3
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from evercurrent.ingestion.synthetic import generate_batch
from evercurrent.ingestion.synthetic_schemas import PHASES, Phase
from evercurrent.llm.tiering import ModelTier

CHANNELS = {
    "mech-design": "C0B8ZNVJW8Z",
    "firmware": "C0B8S7L1JNP",
    "electrical": "C0B90DNP34H",
    "manufacturing": "C0B92789JTE",
    "qa-testing": "C0B8ZNRP8KB",
    "supply-chain": "C0B8XTSFL58",
    "compliance": "C0B9ST0DA1W",
}


def _phase_for(key: str) -> Phase:
    for p in PHASES:
        if p.key == key.lower():
            return p
    return PHASES[1]


async def _post(client: httpx.AsyncClient, token: str, channel_id: str, text: str) -> None:
    r = await client.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel_id, "text": text},
    )
    body: dict[str, Any] = r.json()
    if not body.get("ok"):
        print(f"post failed: {body.get('error')}")
    else:
        print(f"posted ts={body.get('ts')} channel={channel_id}: {text[:50]}")


async def main() -> None:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token or not token.startswith("xoxp-"):
        raise SystemExit("SLACK_USER_TOKEN (xoxp-...) not set; see module docstring")

    channel_name = os.environ.get("CHATTER_CHANNEL", "mech-design")
    channel_id = CHANNELS.get(channel_name, channel_name)
    count = int(os.environ.get("CHATTER_COUNT", "1"))
    interval = float(os.environ.get("CHATTER_INTERVAL", "3"))
    phase = _phase_for(os.environ.get("CHATTER_PHASE", "fcs"))

    messages = await generate_batch(
        channel=channel_name,
        phase=phase,
        count=count,
        threads=1,
        tier=ModelTier.TAGGING,
    )
    if not messages:
        raise SystemExit("generate_batch returned no messages")

    # generate_batch returns a whole thread; cap to the requested count.
    to_post = messages[:count]
    async with httpx.AsyncClient(timeout=20.0) as client:
        for i, m in enumerate(to_post):
            await _post(client, token, channel_id, m.text)
            if i < len(to_post) - 1:
                await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
