"""Generate a rich historical Slack corpus and post it as personas.

Claude (Haiku) writes phase-aware chatter per channel; we post it to real
Slack in phase order (EVT -> FCS) so the Slack `ts` is monotonic. After you
Sync (backfill ingests it), run `backdate_corpus.py` to spread posted_at
across the project timeline. Messages live in Slack; the pipeline is real.

Env: SLACK_DEMO_BOT_TOKEN. Optional CORPUS_COUNT_PER (per channel/phase, def 30).

Run:  docker compose exec api python /tmp/generate_corpus.py
"""

from __future__ import annotations

import asyncio
import contextlib
import os

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient
from evercurrent.ingestion.personas import BY_NAME
from evercurrent.ingestion.synthetic import CHANNEL_TOPICS, generate_batch
from evercurrent.ingestion.synthetic_schemas import PHASES


async def _post(
    client: SlackClient, channel_id: str, author: str, text: str, thread_ts: str | None
) -> str | None:
    persona = BY_NAME.get(author)
    try:
        resp = await client.chat_post_message(
            channel=channel_id,
            text=text,
            username=author,
            icon_emoji=persona.emoji if persona else None,
            thread_ts=thread_ts,
        )
        return str(resp.get("ts")) if resp.get("ts") else None
    except SlackAPIError as exc:
        print(f"  post failed (#{author}): {exc.error}")
        return None


async def main() -> None:
    token = get_settings().slack_demo_bot_token
    if not token:
        raise SystemExit("SLACK_DEMO_BOT_TOKEN not set")
    count_per = int(os.environ.get("CORPUS_COUNT_PER", "30"))

    client = SlackClient(bot_token=token)
    posted = 0
    try:
        all_ch = await client.list_all_channels()
        channels = {c.name: c.id for c in all_ch if not c.is_archived}
        targets = [(n, cid) for n, cid in channels.items() if n in CHANNEL_TOPICS]
        if not targets:
            raise SystemExit(f"no matching channels. have: {sorted(channels)}")
        for _name, cid in targets:
            with contextlib.suppress(SlackAPIError):
                await client.conversations_join(channel=cid)

        for phase in PHASES:
            for name, cid in targets:
                msgs = await generate_batch(channel=name, phase=phase, count=count_per)
                roots: dict[str, str] = {}
                for m in msgs:
                    thread_ts = roots.get(m.thread_key) if m.thread_key else None
                    ts = await _post(client, cid, m.author, m.text, thread_ts)
                    if ts:
                        posted += 1
                        if m.thread_key and m.thread_key not in roots:
                            roots[m.thread_key] = ts
                print(f"  [{phase.label}] #{name}: posted {len(msgs)} (total {posted})")
    finally:
        await client.aclose()
    print(f"done. posted {posted} messages across {len(targets)} channels x {len(PHASES)} phases")


if __name__ == "__main__":
    asyncio.run(main())
