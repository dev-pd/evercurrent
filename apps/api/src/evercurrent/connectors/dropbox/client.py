"""Async Dropbox API client.

Wraps the subset of the Dropbox HTTP API the EverCurrent connector needs:

- `exchange_code_for_tokens` — OAuth 2.0 code → access + refresh tokens
- `refresh_access_token` — refresh-token grant
- `list_folder` — list a folder's direct children
- `download` — fetch a file's bytes

Dropbox uses two API hosts: api.dropboxapi.com for RPC, and
content.dropboxapi.com for streaming (download / upload).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
API_BASE = "https://api.dropboxapi.com/2"
CONTENT_BASE = "https://content.dropboxapi.com/2"

_TIMEOUT = httpx.Timeout(30.0)


class DropboxAPIError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"dropbox api {status_code}: {body[:200]}")
        self.status_code = status_code
        self.body = body


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int
    account_id: str
    team_id: str | None


@dataclass(frozen=True)
class FolderEntry:
    id: str
    name: str
    path_lower: str
    is_folder: bool
    size: int
    rev: str | None


async def exchange_code_for_tokens(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> TokenSet:
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
        response = await http.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        raise DropboxAPIError(response.status_code, response.text)
    body = response.json()
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_in=int(body.get("expires_in", 14400)),
        account_id=body.get("account_id", ""),
        team_id=body.get("team_id"),
    )


async def refresh_access_token(
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> TokenSet:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
        response = await http.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        raise DropboxAPIError(response.status_code, response.text)
    body = response.json()
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=refresh_token,
        expires_in=int(body.get("expires_in", 14400)),
        account_id=body.get("account_id", ""),
        team_id=body.get("team_id"),
    )


class DropboxClient:
    """One client per request. Holds the access token.

    Callers should refresh tokens via `refresh_access_token()` and
    construct a new client when the cached token expires.
    """

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    async def _rpc(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.post(f"{API_BASE}{path}", headers=headers, json=body)
        if response.status_code != 200:
            raise DropboxAPIError(response.status_code, response.text)
        return response.json()

    async def list_folder(
        self,
        *,
        path: str = "",
        recursive: bool = False,
    ) -> list[FolderEntry]:
        """List entries directly under `path` (empty string = root)."""
        body: dict[str, Any] = {
            "path": path,
            "recursive": recursive,
            "include_deleted": False,
            "include_mounted_folders": True,
            "include_non_downloadable_files": False,
        }
        result = await self._rpc("/files/list_folder", body)
        entries = [_entry_from_dict(e) for e in result.get("entries", [])]
        cursor = result.get("cursor")
        while result.get("has_more") and cursor:
            result = await self._rpc("/files/list_folder/continue", {"cursor": cursor})
            entries.extend(_entry_from_dict(e) for e in result.get("entries", []))
            cursor = result.get("cursor")
        return entries

    async def list_root_folders(self) -> list[FolderEntry]:
        """Top-level folders only — for the install picker."""
        all_entries = await self.list_folder(path="", recursive=False)
        return [e for e in all_entries if e.is_folder]

    async def download(self, *, path: str) -> bytes:
        """Stream a file's bytes via the content endpoint."""
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Dropbox-API-Arg": json.dumps({"path": path}),
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.post(
                f"{CONTENT_BASE}/files/download",
                headers=headers,
            )
        if response.status_code != 200:
            raise DropboxAPIError(response.status_code, response.text)
        return response.content


def _entry_from_dict(e: dict[str, Any]) -> FolderEntry:
    tag = e.get(".tag", "")
    return FolderEntry(
        id=str(e.get("id", "")),
        name=str(e.get("name", "")),
        path_lower=str(e.get("path_lower", "")),
        is_folder=tag == "folder",
        size=int(e.get("size", 0)) if tag == "file" else 0,
        rev=e.get("rev"),
    )
