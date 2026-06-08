"""Async Google Drive v3 API client.

Thin httpx wrapper. We hand-roll the few endpoints we need (files.list,
files.get, files.export, files.watch, channels.stop) instead of pulling
in `google-api-python-client` because the official client is sync-only
and we'd end up calling it through `asyncio.to_thread` anyway. Token
refresh uses the `oauth2.googleapis.com/token` endpoint directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from evercurrent.connectors.drive.schemas import (
    DriveFile,
    DriveFileList,
    DriveTokenResponse,
    DriveWatchResponse,
)

log = structlog.get_logger(__name__)

_DRIVE_API_BASE = "https://www.googleapis.com"
_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_HTTP_TOO_MANY = 429
_HTTP_BAD = 400


class DriveAPIError(RuntimeError):
    """Raised on a non-2xx response from the Drive API."""

    def __init__(self, method: str, status_code: int, body: str) -> None:
        super().__init__(f"drive {method} -> {status_code}: {body}")
        self.method = method
        self.status_code = status_code
        self.body = body


class DriveClient:
    """Minimal Drive v3 client. Bearer-token auth; refresh handled by caller."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        if client is None:
            headers: dict[str, str] = {}
            if access_token is not None:
                headers["Authorization"] = f"Bearer {access_token}"
            client = httpx.AsyncClient(
                base_url=_DRIVE_API_BASE,
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

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for _attempt in range(3):
            resp = await self._client.request(
                method,
                path,
                params=params,
                json=json_body,
            )
            if resp.status_code == _HTTP_TOO_MANY:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                log.warning("drive.rate_limited", path=path, retry_after=retry_after)
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code >= _HTTP_BAD:
                raise DriveAPIError(f"{method} {path}", resp.status_code, resp.text)
            data: dict[str, Any] = resp.json()
            return data
        raise DriveAPIError(f"{method} {path}", _HTTP_TOO_MANY, "rate_limited_persistent")

    async def files_list(
        self,
        *,
        query: str | None = None,
        page_token: str | None = None,
        page_size: int = 100,
        fields: str = "files(id,name,mimeType,modifiedTime,size,parents),nextPageToken",
    ) -> DriveFileList:
        params: dict[str, Any] = {
            "pageSize": page_size,
            "fields": fields,
        }
        if query is not None:
            params["q"] = query
        if page_token is not None:
            params["pageToken"] = page_token
        data = await self._request_json("GET", "/drive/v3/files", params=params)
        return DriveFileList.model_validate(data)

    async def files_get_metadata(self, file_id: str) -> DriveFile:
        data = await self._request_json(
            "GET",
            f"/drive/v3/files/{file_id}",
            params={"fields": "id,name,mimeType,modifiedTime,size,parents"},
        )
        return DriveFile.model_validate(data)

    async def files_download_bytes(self, file_id: str) -> bytes:
        for _attempt in range(3):
            resp = await self._client.get(
                f"/drive/v3/files/{file_id}",
                params={"alt": "media"},
            )
            if resp.status_code == _HTTP_TOO_MANY:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code >= _HTTP_BAD:
                raise DriveAPIError(
                    f"GET /files/{file_id}?alt=media",
                    resp.status_code,
                    resp.text,
                )
            return resp.content
        raise DriveAPIError(
            f"GET /files/{file_id}?alt=media",
            _HTTP_TOO_MANY,
            "rate_limited_persistent",
        )

    async def files_export_text(self, file_id: str) -> str:
        """Google Docs aren't PDFs — export as plain text."""
        for _attempt in range(3):
            resp = await self._client.get(
                f"/drive/v3/files/{file_id}/export",
                params={"mimeType": "text/plain"},
            )
            if resp.status_code == _HTTP_TOO_MANY:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code >= _HTTP_BAD:
                raise DriveAPIError(
                    f"GET /files/{file_id}/export",
                    resp.status_code,
                    resp.text,
                )
            return resp.text
        raise DriveAPIError(
            f"GET /files/{file_id}/export",
            _HTTP_TOO_MANY,
            "rate_limited_persistent",
        )

    async def files_watch(
        self,
        *,
        file_id: str,
        channel_id: str,
        channel_token: str,
        webhook_url: str,
        ttl_seconds: int = 7 * 24 * 60 * 60,
    ) -> DriveWatchResponse:
        body: dict[str, Any] = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
            "token": channel_token,
            "params": {"ttl": str(ttl_seconds)},
        }
        data = await self._request_json(
            "POST",
            f"/drive/v3/files/{file_id}/watch",
            json_body=body,
        )
        return DriveWatchResponse.model_validate(data)

    async def channels_stop(self, *, channel_id: str, resource_id: str) -> None:
        body = {"id": channel_id, "resourceId": resource_id}
        # channels.stop returns 204 on success; treat any 2xx as ok.
        resp = await self._client.post("/drive/v3/channels/stop", json=body)
        if resp.status_code >= _HTTP_BAD:
            raise DriveAPIError("POST /channels/stop", resp.status_code, resp.text)


async def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    client: httpx.AsyncClient | None = None,
) -> DriveTokenResponse:
    """Trade an OAuth `code` for an access + refresh token pair."""
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
    try:
        resp = await http.post(
            _OAUTH_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code >= _HTTP_BAD:
            raise DriveAPIError("POST /oauth/token", resp.status_code, resp.text)
        return DriveTokenResponse.model_validate(resp.json())
    finally:
        if owns_client:
            await http.aclose()


async def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    client: httpx.AsyncClient | None = None,
) -> DriveTokenResponse:
    """Refresh an expired access token using a stored refresh token."""
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
    try:
        resp = await http.post(
            _OAUTH_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code >= _HTTP_BAD:
            raise DriveAPIError("POST /oauth/token (refresh)", resp.status_code, resp.text)
        return DriveTokenResponse.model_validate(resp.json())
    finally:
        if owns_client:
            await http.aclose()
