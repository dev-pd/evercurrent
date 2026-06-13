from __future__ import annotations

import hmac
import json
from hashlib import sha256
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from evercurrent.auth.deps import SessionDep
from evercurrent.config import get_settings
from evercurrent.connectors.slack.events import handle_event as handle_slack_event
from evercurrent.connectors.slack.tasks import enqueue_route_message
from evercurrent.db.models import Org, OrgMembership

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class Auth0OrgEvent(BaseModel):
    model_config = ConfigDict(strict=True)

    type: Literal["org.created", "org.deleted", "member.added", "member.removed"]
    org_id: str
    org_name: str | None = None
    user_id: str | None = None
    user_email: str | None = None
    user_name: str | None = None


def _verify_signature(body: bytes, signature: str | None) -> None:
    settings = get_settings()
    secret = settings.auth0_webhook_secret
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="webhook secret not configured",
        )
    if signature is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing signature header",
        )
    expected = hmac.new(secret.encode(), body, sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad signature",
        )


async def _handle_org_created(session: SessionDep, payload: Auth0OrgEvent) -> None:
    existing = (
        await session.execute(select(Org).where(Org.auth0_org_id == payload.org_id))
    ).scalar_one_or_none()
    if existing is None:
        session.add(Org(auth0_org_id=payload.org_id, name=payload.org_name or payload.org_id))


async def _handle_org_deleted(session: SessionDep, payload: Auth0OrgEvent) -> None:
    existing = (
        await session.execute(select(Org).where(Org.auth0_org_id == payload.org_id))
    ).scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)


async def _handle_member_added(session: SessionDep, payload: Auth0OrgEvent) -> None:
    if payload.user_id is None or payload.user_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member.added requires user_id and user_email",
        )
    org_row = (
        await session.execute(select(Org).where(Org.auth0_org_id == payload.org_id))
    ).scalar_one_or_none()
    if org_row is None:
        org_row = Org(auth0_org_id=payload.org_id, name=payload.org_id)
        session.add(org_row)
        await session.flush()
    existing_membership = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org_row.id,
                OrgMembership.auth0_user_id == payload.user_id,
            ),
        )
    ).scalar_one_or_none()
    if existing_membership is None:
        session.add(
            OrgMembership(
                org_id=org_row.id,
                auth0_user_id=payload.user_id,
                display_name=payload.user_name or payload.user_email,
                email=payload.user_email,
            ),
        )


async def _handle_member_removed(session: SessionDep, payload: Auth0OrgEvent) -> None:
    if payload.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member.removed requires user_id",
        )
    org_row = (
        await session.execute(select(Org).where(Org.auth0_org_id == payload.org_id))
    ).scalar_one_or_none()
    if org_row is None:
        return
    membership = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org_row.id,
                OrgMembership.auth0_user_id == payload.user_id,
            ),
        )
    ).scalar_one_or_none()
    if membership is not None:
        await session.delete(membership)


@router.post("/auth0")
async def auth0_webhook(
    request: Request,
    session: SessionDep,
    x_evercurrent_signature: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    body = await request.body()
    _verify_signature(body, x_evercurrent_signature)
    payload = Auth0OrgEvent.model_validate_json(body)

    handlers = {
        "org.created": _handle_org_created,
        "org.deleted": _handle_org_deleted,
        "member.added": _handle_member_added,
        "member.removed": _handle_member_removed,
    }
    handler = handlers[payload.type]
    await handler(session, payload)
    await session.commit()
    return {"ok": True}


@router.post("/slack")
async def slack_webhook(
    request: Request,
    session: SessionDep,
    x_slack_signature: Annotated[str | None, Header()] = None,
    x_slack_request_timestamp: Annotated[str | None, Header()] = None,
) -> Response:
    body = await request.body()
    settings = get_settings()
    result = await handle_slack_event(
        session=session,
        settings=settings,
        body=body,
        timestamp=x_slack_request_timestamp,
        signature=x_slack_signature,
        enqueue_route_message=enqueue_route_message,
    )
    return Response(
        content=json.dumps(result.body),
        status_code=result.status_code,
        media_type="application/json",
    )
