"""Pydantic strict models for the Slack payload shapes we consume.

Only the subset of fields we actually read is modelled. Slack adds
fields liberally; `extra='ignore'` lets new ones slip past without
breaking ingest.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SlackEventInner(BaseModel):
    """The inner `event` object in an Events API envelope."""

    model_config = ConfigDict(strict=True, extra="ignore")

    type: str
    subtype: str | None = None
    ts: str
    thread_ts: str | None = None
    channel: str | None = None
    user: str | None = None
    text: str | None = None
    bot_id: str | None = None


class SlackEventEnvelope(BaseModel):
    """The outer Events API envelope Slack POSTs to our webhook."""

    model_config = ConfigDict(strict=True, extra="ignore")

    type: str  # "event_callback" | "url_verification" | future Slack values
    token: str | None = None
    team_id: str | None = None
    api_app_id: str | None = None
    event: SlackEventInner | None = None
    event_id: str | None = None
    event_time: int | None = None
    challenge: str | None = None


class SlackOAuthResponse(BaseModel):
    """Strict-typed `oauth.v2.access` response (subset we care about)."""

    model_config = ConfigDict(strict=True, extra="ignore")

    ok: bool
    access_token: str | None = None
    token_type: str | None = None
    scope: str | None = None
    bot_user_id: str | None = None
    app_id: str | None = None
    team: dict[str, str] | None = None
    authed_user: dict[str, str] | None = None
    error: str | None = None


class SlackChannelSummary(BaseModel):
    """One channel row from `conversations.list`."""

    model_config = ConfigDict(strict=True, extra="ignore")

    id: str
    name: str = Field(default="")
    is_channel: bool = False
    is_group: bool = False
    is_im: bool = False
    is_private: bool = False
    is_archived: bool = False
