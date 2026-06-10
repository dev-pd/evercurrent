"""Connectors API: install, list, channel toggles.

Webhook endpoint for inbound Slack events lives in `webhooks.py` so
all webhook surfaces share the same prefix + tag. This router holds
the user-facing connector management endpoints.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from starlette.responses import RedirectResponse

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.config import get_settings
from evercurrent.connectors.drive import install as drive_install
from evercurrent.connectors.drive.client import DriveClient
from evercurrent.connectors.drive.watch import register_watch
from evercurrent.connectors.drive.webhook import discover_folders
from evercurrent.connectors.dropbox import install as dropbox_install
from evercurrent.connectors.dropbox.client import DropboxAPIError, DropboxClient
from evercurrent.connectors.dropbox.install import decode_token_blob
from evercurrent.connectors.dropbox.sync import sync_folder as dropbox_sync_folder
from evercurrent.connectors.slack import install as slack_install
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


class ConnectorSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: str
    status: str
    external_team_id: str | None
    channels_count: int
    message_count: int


class InstallResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    redirect_url: str


class ChannelTogglePayload(BaseModel):
    model_config = ConfigDict(strict=True)

    ingest: bool


class DriveFolderSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    name: str


class DriveFolderSelection(BaseModel):
    model_config = ConfigDict(strict=True)

    ingest: bool = True
    name: str | None = None


def _vault() -> TokenVault:
    settings = get_settings()
    if settings.connector_secret_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="connector_secret_key not configured",
        )
    return TokenVault(settings.connector_secret_key)


@router.get("")
async def list_connectors(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[ConnectorSummary]:
    rows = (
        await session.execute(
            select(models.Connector).where(models.Connector.org_id == current_user.org_id),
        )
    ).scalars().all()

    out: list[ConnectorSummary] = []
    for row in rows:
        channel_count = (
            await session.execute(
                select(func.count()).select_from(models.ConnectorChannel).where(
                    models.ConnectorChannel.connector_id == row.id,
                ),
            )
        ).scalar_one()
        out.append(
            ConnectorSummary(
                id=row.id,
                kind=row.kind,
                status=row.status,
                external_team_id=row.external_team_id,
                channels_count=int(channel_count),
                message_count=0,
            ),
        )
    return out


@router.post("/slack/install")
async def slack_install_start(current_user: CurrentUserDep) -> InstallResponse:
    settings = get_settings()
    if settings.slack_client_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="slack_client_id not configured",
        )
    url = slack_install.build_install_url(
        org_id=current_user.org_id,
        settings=settings,
    )
    return InstallResponse(redirect_url=url)


@router.get("/slack/oauth/callback")
async def slack_oauth_callback(
    session: SessionDep,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    settings = get_settings()
    try:
        connector_id = await slack_install.exchange_and_persist(
            session=session,
            settings=settings,
            vault=_vault(),
            code=code,
            state_token=state,
            installed_by_membership_id=None,
        )
    except slack_install.InstallStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await session.commit()
    log.info("slack.install.callback_complete", connector_id=str(connector_id))

    return RedirectResponse(url="/connectors", status_code=status.HTTP_302_FOUND)


@router.post("/drive/install")
async def drive_install_start(current_user: CurrentUserDep) -> InstallResponse:
    settings = get_settings()
    if settings.google_client_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google_client_id not configured",
        )
    url = drive_install.build_install_url(
        org_id=current_user.org_id,
        settings=settings,
    )
    return InstallResponse(redirect_url=url)


@router.get("/drive/oauth/callback")
async def drive_oauth_callback(
    session: SessionDep,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    settings = get_settings()
    try:
        connector_id = await drive_install.exchange_and_persist(
            session=session,
            settings=settings,
            vault=_vault(),
            code=code,
            state_token=state,
            installed_by_membership_id=None,
        )
    except drive_install.InstallStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await session.commit()
    log.info("drive.install.callback_complete", connector_id=str(connector_id))

    return RedirectResponse(url="/connectors", status_code=status.HTTP_302_FOUND)


# ----- Dropbox ------------------------------------------------------------


class DropboxFolderSummary(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    name: str
    path: str


class DropboxFolderSelection(BaseModel):
    model_config = ConfigDict(strict=True)
    folder_path: str
    folder_name: str


class DropboxSyncResult(BaseModel):
    model_config = ConfigDict(strict=True)
    total_pdfs: int
    ingested: int
    skipped: int
    failed: int


@router.post("/dropbox/install")
async def dropbox_install_start(current_user: CurrentUserDep) -> InstallResponse:
    settings = get_settings()
    if settings.dropbox_client_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dropbox_client_id not configured",
        )
    url = dropbox_install.build_install_url(
        org_id=current_user.org_id,
        settings=settings,
    )
    return InstallResponse(redirect_url=url)


@router.get("/dropbox/oauth/callback")
async def dropbox_oauth_callback(
    session: SessionDep,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    settings = get_settings()
    try:
        connector_id = await dropbox_install.exchange_and_persist(
            session=session,
            settings=settings,
            vault=_vault(),
            code=code,
            state_token=state,
            installed_by_membership_id=None,
        )
    except dropbox_install.InstallStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await session.commit()
    log.info("dropbox.install.callback_complete", connector_id=str(connector_id))
    return RedirectResponse(url="/connectors", status_code=status.HTTP_302_FOUND)


@router.get("/{connector_id}/dropbox/folders")
async def list_dropbox_folders(
    session: SessionDep,
    connector_id: uuid.UUID,
) -> list[DropboxFolderSummary]:
    connector = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.id == connector_id,
                models.Connector.kind == "dropbox",
            ),
        )
    ).scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    blob = decode_token_blob(_vault().decrypt(connector.credentials_secret))
    client = DropboxClient(access_token=str(blob["access_token"]))
    try:
        entries = await client.list_root_folders()
    except DropboxAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"dropbox api error: {exc}",
        ) from exc
    return [
        DropboxFolderSummary(id=e.id, name=e.name, path=e.path_lower)
        for e in entries
    ]


@router.post("/{connector_id}/dropbox/sync")
async def sync_dropbox_folder(
    session: SessionDep,
    connector_id: uuid.UUID,
    payload: DropboxFolderSelection,
) -> DropboxSyncResult:
    settings = get_settings()
    try:
        result = await dropbox_sync_folder(
            session=session,
            settings=settings,
            vault=_vault(),
            connector_id=connector_id,
            folder_path=payload.folder_path,
        )
        await session.commit()
    except DropboxAPIError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"dropbox api error: {exc}",
        ) from exc
    return DropboxSyncResult(**result)


# ----- Drive folder picker (existing) -------------------------------------


@router.get("/{connector_id}/folders")
async def list_drive_folders(
    connector_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[DriveFolderSummary]:
    connector = await session.get(models.Connector, connector_id)
    if connector is None or connector.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="connector not found",
        )
    folders = await discover_folders(
        session=session,
        settings=get_settings(),
        vault=_vault(),
        connector_id=connector_id,
    )
    return [DriveFolderSummary(**f) for f in folders]


@router.post("/{connector_id}/folders/{folder_id}")
async def select_drive_folder(
    connector_id: uuid.UUID,
    folder_id: str,
    payload: DriveFolderSelection,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """Register a watch on the chosen folder + persist a connector_channels row."""
    connector = await session.get(models.Connector, connector_id)
    if connector is None or connector.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="connector not found",
        )
    settings = get_settings()
    vault = _vault()
    import json as _json

    blob = vault.decrypt(connector.credentials_secret)
    token_payload = _json.loads(blob)
    access_token = str(token_payload["access_token"])
    client = DriveClient(access_token=access_token)
    try:
        record = await register_watch(
            session=session,
            settings=settings,
            drive_client=client,
            connector_id=connector_id,
            folder_id=folder_id,
            folder_name=payload.name,
        )
    finally:
        await client.aclose()
    await session.commit()
    return {"channel_id": record.channel_id, "folder_id": folder_id}


@router.post("/{connector_id}/channels/{external_id}")
async def toggle_channel_ingest(
    connector_id: uuid.UUID,
    external_id: str,
    payload: ChannelTogglePayload,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict[str, bool]:
    row = (
        await session.execute(
            select(models.ConnectorChannel).where(
                models.ConnectorChannel.connector_id == connector_id,
                models.ConnectorChannel.external_id == external_id,
            ),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="channel not found",
        )
    row.ingest = payload.ingest
    await session.commit()
    log.info(
        "slack.channel.toggle",
        connector_id=str(connector_id),
        external_id=external_id,
        ingest=payload.ingest,
        membership_id=str(current_user.membership_id),
    )
    return {"ingest": row.ingest}
