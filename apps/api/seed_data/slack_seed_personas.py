"""Post rich, cross-functional Atlas-v2 chatter as distinct personas.

One bot posts with a per-message `username` override (needs the
chat:write.customize scope), so each persona shows up as its own author.
Conversations are threaded and spread across whatever channels exist, so
after Sync each persona gets dedicated, role-relevant content and the
per-member digests visibly differ.

Uses SLACK_DEMO_BOT_TOKEN directly (not the connector DB row), so it runs
before connecting or after a DB nuke. The bot auto-joins public channels.

Run:  docker compose exec api python -m seed_data.slack_seed_personas
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient

EMOJI = {
    "Mei Chen": ":zap:",
    "Lin Zhao": ":wrench:",
    "Raj Patel": ":computer:",
    "Sara Kim": ":test_tube:",
    "Tom Alvarez": ":package:",
    "Priya Nair": ":dart:",
}


@dataclass(frozen=True)
class Thread:
    channel_hint: str
    root_author: str
    root_text: str
    replies: list[tuple[str, str]] = field(default_factory=list)


THREADS: list[Thread] = [
    Thread(
        "electrical",
        "Mei Chen",
        "Decision: switching Orion 18650 sourcing from Murata NCA to Samsung "
        "INR18650-35E to dodge the 14-week post-CNY lead time on the Murata cells.",
        [
            (
                "Raj Patel",
                "Heads up — the BMS SOC curves are tuned for Murata chemistry. "
                "They'll need re-characterization for the Samsung cells before we ship.",
            ),
            (
                "Sara Kim",
                "That re-char blocks DVT exit on my side. HTOL on the new cells "
                "is 4-6 weeks minimum.",
            ),
            (
                "Mei Chen",
                "Understood. The 100 mAh/cell delta also eats ~2.8% of our 3% "
                "energy margin — we're at ~0.2% headroom against the 100 Wh pack target.",
            ),
            (
                "Priya Nair",
                "Let's get the cell-swap qual plan on the calendar. BMS re-char "
                "+ HTOL could threaten the Sep 15 FCS.",
            ),
        ],
    ),
    Thread(
        "electrical",
        "Mei Chen",
        "Confirmed: the 3V3 buck is under-spec for our actual load. Peak draw hits "
        "1.4A, the regulator is rated 1.2A continuous. Need a BOM change.",
        [
            (
                "Sara Kim",
                "That matches the field data — one EVT unit's voltage-sense ADC "
                "reads ~30mV high across all 4 cells. Smells like the same regulator issue.",
            ),
            (
                "Raj Patel",
                "Firmware can throttle the radio duty cycle to cap peak draw as "
                "a stopgap, but it's a band-aid, not a fix.",
            ),
        ],
    ),
    Thread(
        "mech",
        "Lin Zhao",
        "BRK-A1 chassis bracket material switched to AL-7075-T6 per ECO-178. "
        "Affects the chassis and the actuator mount.",
        [
            (
                "Tom Alvarez",
                "ECO-178 released to manufacturing. That closes out the "
                "AlumWest alloy change — supply and mfg both impacted.",
            ),
            (
                "Lin Zhao",
                "Also bumped the standoff height 0.4mm -> 1.0mm for the EVT "
                "build, captured in ECO-181.",
            ),
            (
                "Sara Kim",
                "Need updated drawings before I can re-run the drop test. The "
                "0.4mm delta changes the impact geometry.",
            ),
        ],
    ),
    Thread(
        "firmware",
        "Raj Patel",
        "1.0.1 firmware approved for OTA to all DVT units — touches power_management "
        "and hardware_rev.",
        [
            (
                "Sara Kim",
                "I'll gate the OTA behind the thermal regression suite. Last "
                "build regressed idle temps 3°C.",
            ),
            (
                "Mei Chen",
                "Make sure the power_management changes don't touch the buck "
                "PWM frequency — we're already marginal on EMI there.",
            ),
        ],
    ),
    Thread(
        "supply",
        "Tom Alvarez",
        "AlumWest lead time confirmed at 14 weeks. I'll issue the PO once the cell "
        "decision is locked — don't want to commit alloy before the chemistry is final.",
        [
            (
                "Priya Nair",
                "Cell decision lands this week. Hold the PO until Thursday's "
                "review, then release same day so we protect the build slot.",
            ),
            (
                "Tom Alvarez",
                "Copy. Also flagging: the connector vendor (AC-2401-09) "
                "quoted $1.18/each at 25k units, up 9% from last quarter.",
            ),
        ],
    ),
    Thread(
        "general",
        "Priya Nair",
        "Atlas v2 status: day 43 of DVT. Reliability and test are the active phase "
        "concerns. FCS target holds at Sep 15 — but the cell swap is the critical path.",
        [
            (
                "Sara Kim",
                "DVT exit is blocked from my side — reliability is green but "
                "PVT build readiness is at risk on thermal margin.",
            ),
            (
                "Mei Chen",
                "Energy margin is the other risk. Cell swap buys us lead-time "
                "but costs us headroom. Trade-off review needed.",
            ),
            (
                "Lin Zhao",
                "Mechanical is green. Chassis ECOs are closed, drop test pending new drawings.",
            ),
            ("Tom Alvarez", "Supply is gated on the cell decision. Everything else is lined up."),
        ],
    ),
]

BROADCAST: list[tuple[str, str]] = [
    (
        "Sara Kim",
        "Beta week 2 incident report: 1 unit returned, customer cited "
        "intermittent power-off under load. Root cause likely the 3V3 buck.",
    ),
    (
        "Priya Nair",
        "Reminder: phase-gate review Friday 10am. Bring your top risk and "
        "its mitigation. We close DVT or we don't.",
    ),
    ("Raj Patel", "Pushed 0.9.0 -> 1.0.0 release notes. 1.0.1 OTA staged behind QA gate."),
]


async def _post(
    client: SlackClient, channel: str, author: str, text: str, thread_ts: str | None = None
) -> str | None:
    try:
        resp = await client.chat_post_message(
            channel=channel,
            text=text,
            username=author,
            icon_emoji=EMOJI.get(author),
            thread_ts=thread_ts,
        )
        return str(resp.get("ts")) if resp.get("ts") else None
    except SlackAPIError as exc:
        print(f"  post failed (#{channel} as {author}): {exc.error}")
        return None


def _pick_channel(hint: str, channels: list[tuple[str, str]], fallback_idx: int) -> str:
    for cid, name in channels:
        if hint in name.lower():
            return cid
    return channels[fallback_idx % len(channels)][0]


async def main() -> None:
    token = get_settings().slack_demo_bot_token
    if not token:
        raise SystemExit("SLACK_DEMO_BOT_TOKEN not set")
    client = SlackClient(bot_token=token)
    posted = 0
    try:
        all_ch = await client.list_all_channels()
        channels = [(c.id, c.name) for c in all_ch if not c.is_archived]
        if not channels:
            raise SystemExit("no channels found")
        for cid, _name in channels:
            with contextlib.suppress(SlackAPIError):
                await client.conversations_join(channel=cid)

        for i, th in enumerate(THREADS):
            cid = _pick_channel(th.channel_hint, channels, i)
            root_ts = await _post(client, cid, th.root_author, th.root_text)
            if root_ts:
                posted += 1
                for author, text in th.replies:
                    if await _post(client, cid, author, text, thread_ts=root_ts):
                        posted += 1

        general = _pick_channel("general", channels, 0)
        for author, text in BROADCAST:
            if await _post(client, general, author, text):
                posted += 1
    finally:
        await client.aclose()
    print(f"done. posted {posted} persona messages across {len(channels)} channels")


if __name__ == "__main__":
    asyncio.run(main())
