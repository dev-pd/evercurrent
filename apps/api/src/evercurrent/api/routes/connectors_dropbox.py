"""Dropbox connector routes: OAuth install/callback and folder selection + sync."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from starlette.responses import RedirectResponse

from evercurrent.api.routes.connectors_shared import InstallResponse, vault
from evercurrent.auth.deps import AdminUserDep, SessionDep
from evercurrent.config import get_settings
from evercurrent.connectors.dropbox import install as dropbox_install
from evercurrent.connectors.dropbox.client import DropboxAPIError, DropboxClient
from evercurrent.connectors.dropbox.sync import (
    ensure_fresh_dropbox_token,
)
from evercurrent.connectors.dropbox.sync import (
    sync_folder as dropbox_sync_folder,
)
from evercurrent.db.repositories.connectors import ConnectorRepository
from evercurrent.db.session import admin_session_scope

log = structlog.get_logger(__name__)

router = APIRouter(tags=["connectors"])


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
async def dropbox_install_start(current_user: AdminUserDep) -> InstallResponse:
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
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    settings = get_settings()
    async with admin_session_scope() as session:
        try:
            connector_id = await dropbox_install.exchange_and_persist(
                session=session,
                settings=settings,
                vault=vault(),
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

    # Ingest on connect — Dropbox has no separate sync button, so connecting
    # from the UI is the trigger. Pulls the default folder into documents/chunks.
    from evercurrent.jobs.celery_app import celery_app

    celery_app.send_task(
        "evercurrent.sync_dropbox_connector",
        kwargs={"connector_id": str(connector_id)},
    )
    log.info("dropbox.install.callback_complete", connector_id=str(connector_id))
    return RedirectResponse(
        url=f"{get_settings().app_base_url}/settings",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/{connector_id}/dropbox/folders")
async def list_dropbox_folders(
    session: SessionDep,
    current_user: AdminUserDep,
    connector_id: uuid.UUID,
) -> list[DropboxFolderSummary]:
    _ = current_user
    connector = await ConnectorRepository(session).get_dropbox(connector_id)
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    access_token = await ensure_fresh_dropbox_token(
        session=session,
        settings=get_settings(),
        vault=vault(),
        connector=connector,
    )
    await session.commit()
    client = DropboxClient(access_token=access_token)
    try:
        entries = await client.list_root_folders()
    except DropboxAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"dropbox api error: {exc}",
        ) from exc
    return [DropboxFolderSummary(id=e.id, name=e.name, path=e.path_lower) for e in entries]


@router.post("/{connector_id}/dropbox/sync")
async def sync_dropbox_folder(
    session: SessionDep,
    current_user: AdminUserDep,
    connector_id: uuid.UUID,
    payload: DropboxFolderSelection,
) -> DropboxSyncResult:
    _ = current_user
    settings = get_settings()
    try:
        result = await dropbox_sync_folder(
            session=session,
            settings=settings,
            vault=vault(),
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
