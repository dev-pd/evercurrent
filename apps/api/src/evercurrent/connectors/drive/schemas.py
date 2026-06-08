"""Pydantic strict models for the Drive API payloads we read.

Only the subset of fields the connector actually uses is modelled. Drive
adds fields liberally; `extra='ignore'` keeps the schemas forward-compatible.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DriveTokenResponse(BaseModel):
    """`oauth2.googleapis.com/token` exchange response."""

    model_config = ConfigDict(strict=True, extra="ignore")

    access_token: str
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None
    token_type: str | None = None


class DriveFile(BaseModel):
    """A single `files.get` / `files.list` entry."""

    model_config = ConfigDict(strict=True, extra="ignore")

    id: str
    name: str = Field(default="")
    mime_type: str = Field(default="", alias="mimeType")
    size: int | None = None
    modified_time: str | None = Field(default=None, alias="modifiedTime")
    parents: list[str] = Field(default_factory=list)


class DriveFileList(BaseModel):
    """`files.list` response shape (paged)."""

    model_config = ConfigDict(strict=True, extra="ignore")

    files: list[DriveFile] = Field(default_factory=list)
    next_page_token: str | None = Field(default=None, alias="nextPageToken")


class DriveWatchResponse(BaseModel):
    """`files.watch` response shape — defines the registered push channel."""

    model_config = ConfigDict(strict=True, extra="ignore")

    id: str
    resource_id: str = Field(alias="resourceId")
    resource_uri: str | None = Field(default=None, alias="resourceUri")
    expiration: int | None = None
    token: str | None = None
