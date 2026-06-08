"""Async Slack Web API wrapper.

Thin httpx-based client. We use the Web API for OAuth code exchange,
channel discovery, history backfill, and orphan-parent fetch — no
production-grade rate limiter here, just `Retry-After` honoured on
429s. Slack's `slack-sdk` is the obvious alternative, but a focused
wrapper around httpx keeps the dependency surface small and the
mocking path trivial in tests.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import structlog

from evercurrent.connectors.slack.schemas import (
    SlackChannelSummary,
    SlackOAuthResponse,
)

log = structlog.get_logger(__name__)

_SLACK_API_BASE = "https://slack.com/api"
_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class SlackAPIError(RuntimeError):
    """Raised when a Slack API call returns ok=false or a non-2xx HTTP code."""

    def __init__(self, method: str, error: str) -> None:
        super().__init__(f"slack {method} failed: {error}")
        self.method = method
        self.error = error


class SlackClient:
    """Minimal Slack Web API client. Stateless modulo the bot token."""

    def __init__(
        self,
        bot_token: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = bot_token
        # When a client isn't injected (production path), build one with the
        # auth header baked in. Tests inject a MockTransport-backed client.
        if client is None:
            headers: dict[str, str] = {}
            if bot_token is not None:
                headers["Authorization"] = f"Bearer {bot_token}"
            client = httpx.AsyncClient(
                base_url=_SLACK_API_BASE,
                timeout=_DEFAULT_TIMEOUT,
                headers=headers,
            )
            self._owns_client = True
        else:
            self._owns_client = False
        self._client = client

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Slack treats application/x-www-form-urlencoded as preferred for the
        # legacy/web API; we keep that to stay compatible with very old scopes.
        for _attempt in range(3):
            resp = await self._client.post(f"/{method}", data=payload)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                log.warning("slack.rate_limited", method=method, retry_after=retry_after)
                await asyncio.sleep(retry_after)
                continue
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            if not data.get("ok", False):
                err = str(data.get("error", "unknown_error"))
                # Some "errors" are advisory (e.g. `not_in_channel` during
                # backfill); we surface them and let the caller decide.
                raise SlackAPIError(method, err)
            return data
        raise SlackAPIError(method, "rate_limited_persistent")

    async def _get(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        for _attempt in range(3):
            resp = await self._client.get(f"/{method}", params=params)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                log.warning("slack.rate_limited", method=method, retry_after=retry_after)
                await asyncio.sleep(retry_after)
                continue
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            if not data.get("ok", False):
                raise SlackAPIError(method, str(data.get("error", "unknown_error")))
            return data
        raise SlackAPIError(method, "rate_limited_persistent")

    async def oauth_v2_access(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> SlackOAuthResponse:
        """Exchange an OAuth `code` for a bot token. No bot-token auth used."""
        resp = await self._client.post(
            "/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        return SlackOAuthResponse.model_validate(resp.json())

    async def auth_test(self) -> dict[str, Any]:
        return await self._post("auth.test", {})

    async def conversations_list(
        self,
        *,
        cursor: str | None = None,
        limit: int = 200,
        types: str = "public_channel,private_channel",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "types": types}
        if cursor:
            params["cursor"] = cursor
        return await self._get("conversations.list", params)

    async def list_all_channels(self) -> list[SlackChannelSummary]:
        """Paginate `conversations.list` and return the merged channel list."""
        out: list[SlackChannelSummary] = []
        cursor: str | None = None
        while True:
            page = await self.conversations_list(cursor=cursor)
            for raw in page.get("channels", []):
                out.append(SlackChannelSummary.model_validate(raw))
            cursor = page.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return out

    async def conversations_history(
        self,
        *,
        channel: str,
        oldest: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"channel": channel, "limit": limit}
        if oldest is not None:
            params["oldest"] = oldest
        if cursor is not None:
            params["cursor"] = cursor
        return await self._get("conversations.history", params)

    async def conversations_replies(
        self,
        *,
        channel: str,
        ts: str,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"channel": channel, "ts": ts, "limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        return await self._get("conversations.replies", params)

    async def users_info(self, *, user: str) -> dict[str, Any]:
        return await self._get("users.info", {"user": user})

    async def chat_post_message(
        self,
        *,
        channel: str,
        text: str,
        username: str | None = None,
        icon_emoji: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if username is not None:
            payload["username"] = username
        if icon_emoji is not None:
            payload["icon_emoji"] = icon_emoji
        if blocks is not None:
            # Slack wants `blocks` as JSON-encoded when posting via form data.
            payload["blocks"] = json.dumps(blocks)
        return await self._post("chat.postMessage", payload)
