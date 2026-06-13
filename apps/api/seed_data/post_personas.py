"""Post realistic Atlas-v2 chatter into Slack as distinct personas.

One bot posts with a per-message `username` override, so each persona shows up
as its own author. After running, hit Sync in the app: each persona becomes a
member and the pipeline produces their cards/digests. Real Slack, real pipeline.

Run:  docker compose exec api python -m seed_data.post_personas
Needs: a connected Slack connector + the bot in a channel + the
       chat:write.customize scope (for the username override).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db.session import admin_session_scope

PERSONAS: list[tuple[str, str, list[str]]] = [
    (
        "Mei Chen",
        ":zap:",
        [
            "Decision: switching Orion 18650 sourcing from Murata NCA to Samsung "
            "INR18650-35E to dodge the 14-week post-CNY lead time.",
            "Heads up — the 100 mAh/cell delta eats ~2.8% of our ~3% energy margin. "
            "We're at ~0.2% headroom against the 100 Wh pack target.",
        ],
    ),
    (
        "Lin Zhao",
        ":wrench:",
        [
            "BRK-A1 chassis bracket material switched to AL-7075-T6 per ECO-178. "
            "Affects chassis + the actuator mount.",
            "Standoff height bumped 0.4mm -> 1.0mm for the EVT build, captured in ECO-181.",
        ],
    ),
    (
        "Raj Patel",
        ":computer:",
        [
            "1.0.1 firmware approved for OTA to all DVT units — touches power_management "
            "and hardware_rev.",
            "Reminder: the BMS SOC curves are still tuned for Murata chemistry. They need "
            "re-characterization for the Samsung cells before we ship.",
        ],
    ),
    (
        "Sara Kim",
        ":test_tube:",
        [
            "DVT exit is blocked — reliability is green but PVT build readiness is at risk "
            "on thermal margin.",
            "One EVT unit's voltage-sense ADC reads ~30mV high across all 4 cells. Smells "
            "like a regulator BOM issue.",
        ],
    ),
    (
        "Tom Alvarez",
        ":package:",
        [
            "ECO-178 released to manufacturing, closing out the AlumWest alloy change. "
            "Supply + mfg impacted.",
            "AlumWest lead time confirmed at 14 weeks. I'll issue the PO once the cell "
            "decision is locked.",
        ],
    ),
    (
        "Priya Nair",
        ":dart:",
        [
            "Atlas v2 is on day 43 of DVT — reliability and test are the active phase "
            "concerns. FCS target is Sep 15.",
            "Let's get the cell-swap qual plan on the calendar — BMS re-char + HTOL could "
            "eat 4-8 weeks and threaten FCS.",
        ],
    ),
]


async def main() -> None:
    settings = get_settings()
    if settings.connector_secret_key is None:
        msg = "CONNECTOR_SECRET_KEY not set"
        raise SystemExit(msg)
    vault = TokenVault(settings.connector_secret_key)

    async with admin_session_scope() as session:
        conn = (
            await session.execute(
                text("SELECT credentials_secret FROM connectors WHERE kind = 'slack' LIMIT 1"),
            )
        ).first()
        if conn is None:
            raise SystemExit("no slack connector — connect Slack first")
        token = vault.decrypt(conn[0])
        channels = (
            (await session.execute(text("SELECT external_id, name FROM connector_channels")))
            .all()
        )
    if not channels:
        raise SystemExit("no channels — run Sync once so channels are discovered")

    client = SlackClient(bot_token=token)
    posted = 0
    failed_channels: set[str] = set()
    try:
        for name, emoji, msgs in PERSONAS:
            for m in msgs:
                for ext_id, ch_name in channels:
                    if ext_id in failed_channels:
                        continue
                    try:
                        await client.chat_post_message(
                            channel=ext_id,
                            text=m,
                            username=name,
                            icon_emoji=emoji,
                        )
                        posted += 1
                        break
                    except Exception as exc:  # noqa: BLE001, PERF203
                        failed_channels.add(ext_id)
                        print(f"  channel {ch_name} unusable: {exc}")
    finally:
        await client.aclose()
    print(f"posted {posted} persona messages")


if __name__ == "__main__":
    asyncio.run(main())
