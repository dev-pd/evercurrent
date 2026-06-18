"""Delete every deletable message from all Slack channels.

The bot token (SLACK_DEMO_BOT_TOKEN) always lists channels + reads history (it
has the scopes). Deletion runs in two passes with whichever token owns the
message: pass 1 deletes with the bot token (bot-posted messages), pass 2 deletes
with the user token (SLACK_USER_TOKEN, if set) — the real Prasad user's own
messages. The user token can't list channels (missing scope), so the bot always
does the enumeration; the user token is used only for chat.delete.

Run:  docker compose exec api python -m evercurrent.scripts.slack_wipe
"""

from __future__ import annotations

import asyncio
import contextlib
import os

from evercurrent.config import get_settings
from evercurrent.connectors.slack.client import SlackAPIError, SlackClient

_UNDELETABLE = {"message_not_found", "cant_delete_message", "channel_not_found"}


async def _delete_ts(deleter: SlackClient, channel: str, ts: str) -> bool:
    try:
        await deleter.chat_delete(channel=channel, ts=ts)
        return True
    except SlackAPIError as exc:
        # A token can only delete its own messages; anything it doesn't own
        # (or already gone) is skipped, not fatal.
        if exc.error in _UNDELETABLE:
            return False
        raise


async def _wipe_channel(
    reader: SlackClient,
    deleter: SlackClient,
    channel_id: str,
    name: str,
) -> int:
    deleted = 0
    cursor: str | None = None
    while True:
        page = await reader.conversations_history(channel=channel_id, cursor=cursor, limit=200)
        for msg in page.get("messages", []):
            ts = str(msg.get("ts", ""))
            if not ts:
                continue
            if int(msg.get("reply_count", 0) or 0) > 0:
                deleted += await _wipe_thread(reader, deleter, channel_id, ts)
            if await _delete_ts(deleter, channel_id, ts):
                deleted += 1
        cursor = page.get("response_metadata", {}).get("next_cursor") or None
        if not cursor or not page.get("has_more", False):
            break
    print(f"  #{name}: deleted {deleted}")
    return deleted


async def _wipe_thread(
    reader: SlackClient,
    deleter: SlackClient,
    channel_id: str,
    root_ts: str,
) -> int:
    deleted = 0
    cursor: str | None = None
    while True:
        page = await reader.conversations_replies(channel=channel_id, ts=root_ts, cursor=cursor)
        for msg in page.get("messages", []):
            ts = str(msg.get("ts", ""))
            if not ts or ts == root_ts:
                continue
            if await _delete_ts(deleter, channel_id, ts):
                deleted += 1
        cursor = page.get("response_metadata", {}).get("next_cursor") or None
        if not cursor or not page.get("has_more", False):
            break
    return deleted


async def _wipe(reader: SlackClient, deleter: SlackClient, label: str) -> int:
    """Enumerate via `reader` (bot — has the scopes), delete via `deleter`."""
    total = 0
    channel_count = 0
    channels = await reader.list_all_channels()
    channel_count = len(channels)
    for ch in channels:
        with contextlib.suppress(SlackAPIError):
            await reader.conversations_join(channel=ch.id)
        total += await _wipe_channel(reader, deleter, ch.id, ch.name)
    print(f"[{label}] deleted {total} messages across {channel_count} channels")
    return total


async def main() -> None:
    bot_token = get_settings().slack_demo_bot_token
    if not bot_token:
        raise SystemExit("SLACK_DEMO_BOT_TOKEN not set")
    user_token = os.environ.get("SLACK_USER_TOKEN")

    bot = SlackClient(bot_token=bot_token)
    user = SlackClient(bot_token=user_token) if user_token else None
    total = 0
    try:
        total += await _wipe(bot, bot, "bot")
        if user is not None:
            total += await _wipe(bot, user, "user")
        else:
            print("SLACK_USER_TOKEN not set — skipping user-message pass")
    finally:
        await bot.aclose()
        if user is not None:
            await user.aclose()

    print(f"done. deleted {total} messages total")


if __name__ == "__main__":
    asyncio.run(main())
