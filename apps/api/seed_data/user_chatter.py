"""Post messages to Slack as a real user (xoxp- token) so the live webhook
ingests them.

The demo bot can't drive the webhook: Slack suppresses an app's own bot
messages and the handler skips `bot_message` subtypes. A user-token post is a
normal user message (no subtype, distinct identity) so Slack delivers it to the
Events API -> /webhooks/slack -> route_message.

Env: SLACK_USER_TOKEN (xoxp-..., needs chat:write user scope). Optional
CHATTER_CHANNEL (channel id, default #mech-design), CHATTER_COUNT (per run),
CHATTER_INTERVAL (seconds between posts when count > 1).

Run one message:   docker compose exec -T worker python /app/seed_data/user_chatter.py
Run a burst:       CHATTER_COUNT=5 CHATTER_INTERVAL=3 ... user_chatter.py
Loop from host:    /loop 30s make webhook-chatter
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx

CHANNELS = {
    "mech-design": "C0B8ZNVJW8Z",
    "firmware": "C0B8S7L1JNP",
    "electrical": "C0B90DNP34H",
    "manufacturing": "C0B92789JTE",
    "qa-testing": "C0B8ZNRP8KB",
    "supply-chain": "C0B8XTSFL58",
    "compliance": "C0B9ST0DA1W",
}

MESSAGES = [
    "Bumping the FCS torque spec to 4.2 Nm on the bracket bolts — mech please confirm clearance.",
    "Seeing intermittent I2C dropouts on the BMS rev C boards under thermal soak. Anyone else?",
    "Supplier flagged a 3-week lead time slip on the AL-7075 brackets. Impacts FCS build.",
    "EMC pre-scan failed at 312 MHz, ~4 dB over. Looks like the harness routing near the motor.",
    "Proposing we cut ECO-204 to move the connector 8mm inboard for service access.",
    "DVT exit gate is blocked until we close the gripper resonance finding.",
    "Firmware build 0.9.7 fixes the watchdog reset loop. Flashing the FCS units now.",
    "QA found a hairline crack on bracket BRK-A1 after 500 thermal cycles. Investigating.",
    "Manufacturing wants tolerance on the chassis rail tightened to +/-0.05mm. Pushback?",
    "Compliance: we still need the updated DoC before the FCS shipment can clear customs.",
    "Motor mount FEA shows a stress concentration at the weld toe — revising the fillet.",
    "Can someone own the thermal margin analysis for the high-flux region by Friday?",
]


async def _post(client: httpx.AsyncClient, token: str, channel: str, text: str) -> None:
    r = await client.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel, "text": text},
    )
    body = r.json()
    if not body.get("ok"):
        print(f"post failed: {body.get('error')}")
    else:
        print(f"posted ts={body.get('ts')} channel={channel}: {text[:50]}")


async def main() -> None:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token or not token.startswith("xoxp-"):
        raise SystemExit("SLACK_USER_TOKEN (xoxp-...) not set; see module docstring")

    channel_name = os.environ.get("CHATTER_CHANNEL", "mech-design")
    channel = CHANNELS.get(channel_name, channel_name)
    count = int(os.environ.get("CHATTER_COUNT", "1"))
    interval = float(os.environ.get("CHATTER_INTERVAL", "3"))

    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(count):
            text = MESSAGES[int(time.time() + i) % len(MESSAGES)]
            await _post(client, token, channel, text)
            if i < count - 1:
                await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
