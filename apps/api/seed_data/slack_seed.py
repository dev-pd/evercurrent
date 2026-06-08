"""Post hardware-team demo messages into a real Slack workspace.

Run from the repo root:

    SLACK_DEMO_BOT_TOKEN=xoxb-... uv run --project apps/api \
        python -m apps.api.seed_data.slack_seed

The script expects channels `#mech-design`, `#qa-testing`,
`#supply-chain`, and `#general` to exist and the bot to be invited
(`/invite @evercurrent` in each). Sleeps between posts to stay under
the `chat.postMessage` rate limit.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Final

import structlog

from evercurrent.connectors.slack.client import SlackAPIError, SlackClient

log = structlog.get_logger(__name__)

POST_DELAY_SECONDS: Final[float] = 0.25


@dataclass(frozen=True)
class SeedMessage:
    """A single message in the seed corpus."""

    channel: str
    author: str
    icon_emoji: str
    text: str


# A hand-written hardware-team day. Order is intentional: a supplier
# disruption ripples through mech-design, qa-testing, and general by EOD.
SEED_CORPUS: tuple[SeedMessage, ...] = (
    SeedMessage(
        channel="#supply-chain",
        author="Mei (supply chain)",
        icon_emoji=":truck:",
        text=(
            "ExtruCo strike confirmed. Pulling AlumWest forward for the "
            "chassis extrusions. Need a tolerance trial lot by Monday — "
            "Lin, can you cycle a thermal pass on the trial parts?"
        ),
    ),
    SeedMessage(
        channel="#mech-design",
        author="Sarah (mech)",
        icon_emoji=":wrench:",
        text=(
            "ECO-178 (chassis rib stiffness) looks unaffected by the "
            "AlumWest swap from my side. Modulus delta is inside the "
            "envelope we sized to. Holding the design release."
        ),
    ),
    SeedMessage(
        channel="#qa-testing",
        author="Lin (qa)",
        icon_emoji=":mag:",
        text=(
            "Booking the thermal chamber for Sat AM to run the AlumWest "
            "trial lot. Will publish FAI numbers by EOD Sat. Holding off "
            "on sign-off until then."
        ),
    ),
    SeedMessage(
        channel="#mech-design",
        author="Sarah (mech)",
        icon_emoji=":wrench:",
        text=(
            "Heads up — if AlumWest CTE shifts more than 5%% we'll need "
            "to revisit the rib pitch on ECO-178. Watching Lin's numbers."
        ),
    ),
    SeedMessage(
        channel="#general",
        author="Mei (supply chain)",
        icon_emoji=":truck:",
        text=(
            "Status update for tomorrow's standup: ExtruCo strike, "
            "AlumWest trial lot in flight, FAI by Sat EOD, sign-off "
            "pending Lin."
        ),
    ),
    SeedMessage(
        channel="#qa-testing",
        author="Lin (qa)",
        icon_emoji=":mag:",
        text=(
            "AlumWest FAI cleared at +2.1%% CTE. Inside the rib pitch "
            "envelope. Signing off on the swap. ECO-178 stays on track."
        ),
    ),
    SeedMessage(
        channel="#mech-design",
        author="Sarah (mech)",
        icon_emoji=":wrench:",
        text=(
            "Thanks Lin — releasing ECO-178 to manufacturing. Closing "
            "the loop on the AlumWest swap risk."
        ),
    ),
)


async def post_seed(bot_token: str) -> None:
    client = SlackClient(bot_token=bot_token)
    try:
        for msg in SEED_CORPUS:
            try:
                await client.chat_post_message(
                    channel=msg.channel,
                    text=msg.text,
                    username=msg.author,
                    icon_emoji=msg.icon_emoji,
                )
                log.info(
                    "slack.seed.posted",
                    channel=msg.channel,
                    author=msg.author,
                )
            except SlackAPIError as exc:
                log.error(
                    "slack.seed.failed",
                    channel=msg.channel,
                    author=msg.author,
                    error=exc.error,
                )
            await asyncio.sleep(POST_DELAY_SECONDS)
    finally:
        await client.aclose()


def main() -> int:
    token = os.environ.get("SLACK_DEMO_BOT_TOKEN")
    if not token:
        sys.stderr.write("SLACK_DEMO_BOT_TOKEN not set\n")
        return 2
    asyncio.run(post_seed(token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
