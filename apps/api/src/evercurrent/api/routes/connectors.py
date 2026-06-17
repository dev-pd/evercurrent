"""Connector routes: Slack install/status plus the aggregated connectors router (mounts Dropbox)."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from starlette.responses import RedirectResponse

from evercurrent.api.routes.connectors_dropbox import router as dropbox_router
from evercurrent.api.routes.connectors_shared import InstallResponse, vault
from evercurrent.auth.deps import AdminUserDep, SessionDep
from evercurrent.config import get_settings
from evercurrent.connectors.slack import install as slack_install
from evercurrent.connectors.slack.client import SlackClient
from evercurrent.db import models
from evercurrent.db.repositories.provisioning import ProvisioningRepository
from evercurrent.db.session import admin_session_scope
from evercurrent.ingestion.personas import BY_NAME

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])
router.include_router(dropbox_router)


class ConnectorSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    kind: str
    status: str
    external_team_id: str | None
    channels_count: int
    message_count: int


class ChannelTogglePayload(BaseModel):
    model_config = ConfigDict(strict=True)

    ingest: bool


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


class SyncStartedResult(BaseModel):
    model_config = ConfigDict(strict=True)
    status: str
    connector_id: uuid.UUID


async def _provision_authors(session: SessionDep, client: SlackClient, org_id: uuid.UUID) -> int:
    """Create a member for each Slack author seen in messages, with their real name."""
    repo = ProvisioningRepository(session)
    authors = await repo.unprovisioned_author_names(
        org_id=org_id,
        bot_name=get_settings().slack_app_bot_name,
    )

    provisioned = 0
    for slack_uid in authors:
        # Real Slack user id -> resolve the real name; a persona username is
        # already the display name (one bot posting as personas).
        if slack_uid.startswith("U") and " " not in slack_uid:
            try:
                info = (await client.users_info(user=slack_uid)).get("user", {})
                name = info.get("real_name") or info.get("name") or slack_uid
            except Exception as exc:  # noqa: BLE001
                log.warning("slack.sync.user_lookup_failed", user=slack_uid, error=str(exc))
                name = slack_uid
        else:
            name = slack_uid

        persona = BY_NAME.get(name)
        member_id = await repo.find_member_by_slack_uid(org_id=org_id, slack_uid=slack_uid)
        if member_id is None:
            member_id = await repo.create_slack_member(
                org_id=org_id,
                slack_uid=slack_uid,
                name=name,
                eng_role=persona.eng_role if persona else None,
                owned_subsystems=list(persona.owned_subsystems if persona else []),
            )
            provisioned += 1
        await repo.link_messages_to_member(
            org_id=org_id,
            slack_uid=slack_uid,
            member_id=member_id,
            name=name,
        )
    await session.commit()
    return provisioned


@router.post(
    "/{connector_id}/slack/sync",
    response_model=SyncStartedResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def slack_sync(connector_id: uuid.UUID, current_user: AdminUserDep) -> SyncStartedResult:
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

    from evercurrent.jobs.celery_app import celery_app

    celery_app.send_task(
        "evercurrent.sync_slack_connector",
        kwargs={"connector_id": str(connector_id)},
    )
    return SyncStartedResult(status="started", connector_id=connector_id)


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
                vault=vault(),
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
    return RedirectResponse(
        url=f"{get_settings().app_base_url}/settings",
        status_code=status.HTTP_302_FOUND,
    )


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


@router.delete("/{connector_id}")
async def disconnect_connector(
    connector_id: uuid.UUID,
    session: SessionDep,
    current_user: AdminUserDep,
) -> dict[str, str]:
    connector = (
        await session.execute(
            select(models.Connector).where(
                models.Connector.id == connector_id,
                models.Connector.org_id == current_user.org_id,
            ),
        )
    ).scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    kind = connector.kind
    await session.delete(connector)
    await session.commit()
    log.info(
        "connector.disconnect",
        connector_id=str(connector_id),
        kind=kind,
        membership_id=str(current_user.membership_id),
    )
    return {"status": "disconnected", "kind": kind}
