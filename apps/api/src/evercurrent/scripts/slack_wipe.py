"""Delete every deletable message from all Slack channels.

Two passes: the demo bot token (SLACK_DEMO_BOT_TOKEN) deletes bot-posted
messages, then the user token (SLACK_USER_TOKEN), if set, deletes the real
user's own messages — so `make webhook` chatter from the Prasad user is wiped
too. A token only deletes its own messages; anything neither owns survives.

Run:  docker compose exec api python -m evercurrent.scripts.slack_wipe
"""

from __future__ import annotations

import asyncio
import contextlib
import os

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient

_UNDELETABLE = {"message_not_found", "cant_delete_message", "channel_not_found"}


async def _delete_ts(client: SlackClient, channel: str, ts: str) -> bool:
    try:
        await client.chat_delete(channel=channel, ts=ts)
        return True
    except SlackAPIError as exc:
        if exc.error in _UNDELETABLE:
            return False
        raise


async def _wipe_channel(client: SlackClient, channel_id: str, name: str) -> int:
    deleted = 0
    cursor: str | None = None
    while True:
        page = await client.conversations_history(channel=channel_id, cursor=cursor, limit=200)
        for msg in page.get("messages", []):
            ts = str(msg.get("ts", ""))
            if not ts:
                continue
            if int(msg.get("reply_count", 0) or 0) > 0:
                deleted += await _wipe_thread(client, channel_id, ts)
            if await _delete_ts(client, channel_id, ts):
                deleted += 1
        cursor = page.get("response_metadata", {}).get("next_cursor") or None
        if not cursor or not page.get("has_more", False):
            break
    print(f"  #{name}: deleted {deleted}")
    return deleted


async def _wipe_thread(client: SlackClient, channel_id: str, root_ts: str) -> int:
    deleted = 0
    cursor: str | None = None
    while True:
        page = await client.conversations_replies(channel=channel_id, ts=root_ts, cursor=cursor)
        for msg in page.get("messages", []):
            ts = str(msg.get("ts", ""))
            if not ts or ts == root_ts:
                continue
            if await _delete_ts(client, channel_id, ts):
                deleted += 1
        cursor = page.get("response_metadata", {}).get("next_cursor") or None
        if not cursor or not page.get("has_more", False):
            break
    return deleted


async def _wipe_with_token(token: str, label: str) -> int:
    client = SlackClient(bot_token=token)
    total = 0
    channel_count = 0
    try:
        channels = await client.list_all_channels()
        channel_count = len(channels)
        for ch in channels:
            with contextlib.suppress(SlackAPIError):
                await client.conversations_join(channel=ch.id)
            total += await _wipe_channel(client, ch.id, ch.name)
    finally:
        await client.aclose()
    print(f"[{label}] deleted {total} messages across {channel_count} channels")
    return total


async def main() -> None:
    bot_token = get_settings().slack_demo_bot_token
    if not bot_token:
        raise SystemExit("SLACK_DEMO_BOT_TOKEN not set")
    total = await _wipe_with_token(bot_token, "bot")

    user_token = os.environ.get("SLACK_USER_TOKEN")
    if user_token:
        total += await _wipe_with_token(user_token, "user")
    else:
        print("SLACK_USER_TOKEN not set — skipping user-message pass")

    print(f"done. deleted {total} messages total")


if __name__ == "__main__":
    asyncio.run(main())
