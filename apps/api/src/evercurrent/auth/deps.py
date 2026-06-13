from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.auth.auth0 import Auth0Verifier, InvalidTokenError
from evercurrent.config import get_settings
from evercurrent.db.models import Org, OrgMembership
from evercurrent.db.session import get_sessionmaker
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)

bearer = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        ctx_org_id: uuid.UUID | None = getattr(request.state, "org_id", None)
        if ctx_org_id is not None:
            await set_org_context(session, ctx_org_id)
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_auth0_verifier(request: Request) -> Auth0Verifier:
    verifier: Auth0Verifier | None = getattr(request.app.state, "auth0_verifier", None)
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth0 verifier not configured",
        )
    return verifier


VerifierDep = Annotated[Auth0Verifier, Depends(get_auth0_verifier)]


async def _dev_user(request: Request, session: AsyncSession) -> CurrentUser:
    impersonate = request.headers.get("x-impersonate-user")
    member: OrgMembership | None = None
    if impersonate:
        try:
            member = await session.get(OrgMembership, uuid.UUID(impersonate))
        except ValueError:
            member = None
    if member is None:
        member = (
            await session.execute(
                select(OrgMembership).order_by(OrgMembership.created_at).limit(1),
            )
        ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="no members provisioned",
        )
    request.state.org_id = member.org_id
    await set_org_context(session, member.org_id)
    return CurrentUser(
        org_id=member.org_id,
        membership_id=member.id,
        auth0_user_id=member.auth0_user_id,
        email=member.email,
        display_name=member.display_name,
    )


async def require_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: VerifierDep,
    session: SessionDep,
) -> CurrentUser:
    dev = get_settings().dev_login
    if creds is None:
        if dev:
            return await _dev_user(request, session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    try:
        claims = await verifier.verify(creds.credentials)
    except InvalidTokenError as exc:
        if dev:
            return await _dev_user(request, session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    if claims.org_id is None:
        if dev:
            return await _dev_user(request, session)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="token has no org_id claim",
        )

    org_row = (
        await session.execute(
            select(Org).where(Org.auth0_org_id == claims.org_id),
        )
    ).scalar_one_or_none()
    if org_row is None:
        if dev:
            return await _dev_user(request, session)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="org not provisioned",
        )

    membership_row = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org_row.id,
                OrgMembership.auth0_user_id == claims.sub,
            ),
        )
    ).scalar_one_or_none()
    if membership_row is None:
        membership_row = OrgMembership(
            org_id=org_row.id,
            auth0_user_id=claims.sub,
            email=claims.email or "",
            display_name=claims.name or claims.email or claims.sub,
        )
        session.add(membership_row)
        await session.flush()

    request.state.org_id = org_row.id
    await set_org_context(session, org_row.id)

    return CurrentUser(
        org_id=org_row.id,
        membership_id=membership_row.id,
        auth0_user_id=claims.sub,
        email=claims.email or "",
        display_name=claims.name or claims.email or claims.sub,
    )


class CurrentUser:
    __slots__ = ("auth0_user_id", "display_name", "email", "membership_id", "org_id")

    def __init__(
        self,
        *,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
        auth0_user_id: str,
        email: str,
        display_name: str,
    ) -> None:
        self.org_id = org_id
        self.membership_id = membership_id
        self.auth0_user_id = auth0_user_id
        self.email = email
        self.display_name = display_name


CurrentUserDep = Annotated[CurrentUser, Depends(require_user)]
