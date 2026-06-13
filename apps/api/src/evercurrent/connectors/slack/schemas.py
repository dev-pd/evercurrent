from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SlackEventInner(BaseModel):
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
    model_config = ConfigDict(strict=True, extra="ignore")

    type: str
    token: str | None = None
    team_id: str | None = None
    api_app_id: str | None = None
    event: SlackEventInner | None = None
    event_id: str | None = None
    event_time: int | None = None
    challenge: str | None = None


class SlackOAuthResponse(BaseModel):
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
    model_config = ConfigDict(strict=True, extra="ignore")

    id: str
    name: str = Field(default="")
    is_channel: bool = False
    is_group: bool = False
    is_im: bool = False
    is_private: bool = False
    is_archived: bool = False
