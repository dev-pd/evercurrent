"""Slack deep-link formatting: build a permalink to a message from team/channel/ts.

Pure string formatting (no I/O) — lives with the Slack connector because it
encodes Slack's URL scheme, and is consumed by anything that surfaces a
message's source link (e.g. card source details).
"""

from __future__ import annotations

from evercurrent.config import get_settings


def slack_permalink(team_id: str | None, channel: str | None, ts: str | None) -> str | None:
    """Deep-link straight to the message in the Slack desktop app when we have
    team + channel + ts; fall back to the web archive permalink (universal), then
    a channel-level link. None if we can't even open the channel."""
    if not channel:
        return None
    if team_id and ts:
        return f"slack://channel?team={team_id}&id={channel}&message={ts}"
    domain = get_settings().slack_workspace_domain
    if domain and ts:
        return f"https://{domain}.slack.com/archives/{channel}/p{ts.replace('.', '')}"
    if team_id:
        return f"https://app.slack.com/client/{team_id}/{channel}"
    return None
