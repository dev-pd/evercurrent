from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from starlette.responses import RedirectResponse

from evercurrent.auth.deps import AdminUserDep, SessionDep
from evercurrent.config import get_settings
from evercurrent.connectors.dropbox import install as dropbox_install
from evercurrent.connectors.dropbox.client import DropboxAPIError, DropboxClient
from evercurrent.connectors.dropbox.install import decode_token_blob
from evercurrent.connectors.dropbox.sync import sync_folder as dropbox_sync_folder
from evercurrent.connectors.slack import install as slack_install
from evercurrent.connectors.slack.backfill import backfill_channel
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.db.session import admin_session_scope

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
    current_user: AdminUserDep,
) -> list[ConnectorSummary]:
    rows = (
        (
            await session.execute(
                select(models.Connector).where(models.Connector.org_id == current_user.org_id),
            )
        )
        .scalars()
        .all()
    )

    out: list[ConnectorSummary] = []
    for row in rows:
        channel_count = (
            await session.execute(
                select(func.count())
                .select_from(models.ConnectorChannel)
                .where(
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
async def slack_install_start(current_user: AdminUserDep) -> InstallResponse:
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


class SlackSyncResult(BaseModel):
    model_config = ConfigDict(strict=True)
    channels: int
    raw_events: int
    members: int


async def _provision_authors(session: SessionDep, client: SlackClient, org_id: uuid.UUID) -> int:
    """Create a member for each Slack author seen in messages, with their real name."""
    authors = (
        (
            await session.execute(
                text(
                    "SELECT DISTINCT author_display_name FROM messages "
                    "WHERE org_id = :o AND author_membership_id IS NULL "
                    "AND author_display_name LIKE 'U%'",
                ),
                {"o": str(org_id)},
            )
        )
        .scalars()
        .all()
    )

    provisioned = 0
    for slack_uid in authors:
        try:
            info = (await client.users_info(user=slack_uid)).get("user", {})
            name = info.get("real_name") or info.get("name") or slack_uid
        except Exception as exc:  # noqa: BLE001
            log.warning("slack.sync.user_lookup_failed", user=slack_uid, error=str(exc))
            name = slack_uid

        member_id = (
            await session.execute(
                text("SELECT id FROM org_memberships WHERE org_id = :o AND slack_user_id = :s"),
                {"o": str(org_id), "s": slack_uid},
            )
        ).scalar_one_or_none()
        if member_id is None:
            member_id = (
                await session.execute(
                    text(
                        "INSERT INTO org_memberships "
                        "(org_id, auth0_user_id, slack_user_id, display_name, email, role) "
                        "VALUES (:o, :sub, :s, :n, '', 'member') RETURNING id",
                    ),
                    {"o": str(org_id), "sub": f"slack:{slack_uid}", "s": slack_uid, "n": name},
                )
            ).scalar_one()
            provisioned += 1
        await session.execute(
            text(
                "UPDATE messages SET author_membership_id = :mid, author_display_name = :n "
                "WHERE org_id = :o AND author_display_name = :s",
            ),
            {"mid": str(member_id), "n": name, "o": str(org_id), "s": slack_uid},
        )
    await session.commit()
    return provisioned


@router.post("/{connector_id}/slack/sync", response_model=SlackSyncResult)
async def slack_sync(connector_id: uuid.UUID, current_user: AdminUserDep) -> SlackSyncResult:
    _ = current_user
    async with admin_session_scope() as session:
        connector = (
            await session.execute(
                select(models.Connector).where(
                    models.Connector.id == connector_id,
                    models.Connector.kind == "slack",
                ),
            )
        ).scalar_one_or_none()
        if connector is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

        token = _vault().decrypt(connector.credentials_secret)
        client = SlackClient(bot_token=token)
        channels_done = 0
        raw_total = 0
        members = 0
        try:
            channels = await client.list_all_channels()
            for ch in channels:
                if ch.is_archived:
                    continue
                cc_id = (
                    await session.execute(
                        text(
                            "INSERT INTO connector_channels "
                            "(org_id, connector_id, external_id, name, ingest) "
                            "VALUES (:o, :c, :e, :n, true) "
                            "ON CONFLICT (connector_id, external_id) "
                            "DO UPDATE SET name = EXCLUDED.name RETURNING id",
                        ),
                        {
                            "o": str(connector.org_id),
                            "c": str(connector.id),
                            "e": ch.id,
                            "n": ch.name,
                        },
                    )
                ).scalar_one()
                await session.commit()
                try:
                    summary = await backfill_channel(
                        session=session,
                        vault=_vault(),
                        connector_channel_id=cc_id,
                        days=30,
                        slack_client=client,
                    )
                    raw_total += summary.raw_events_inserted
                    channels_done += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("slack.sync.channel_failed", channel=ch.id, error=str(exc))
            members = await _provision_authors(session, client, connector.org_id)
        finally:
            await client.aclose()
    return SlackSyncResult(channels=channels_done, raw_events=raw_total, members=members)


@router.get("/slack/oauth/callback")
async def slack_oauth_callback(
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    settings = get_settings()
    async with admin_session_scope() as session:
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
    return RedirectResponse(url="/settings", status_code=status.HTTP_302_FOUND)


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
    return RedirectResponse(url="/settings", status_code=status.HTTP_302_FOUND)


@router.get("/{connector_id}/dropbox/folders")
async def list_dropbox_folders(
    session: SessionDep,
    current_user: AdminUserDep,
    connector_id: uuid.UUID,
) -> list[DropboxFolderSummary]:
    _ = current_user
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


@router.post("/{connector_id}/channels/{external_id}")
async def toggle_channel_ingest(
    connector_id: uuid.UUID,
    external_id: str,
    payload: ChannelTogglePayload,
    session: SessionDep,
    current_user: AdminUserDep,
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
