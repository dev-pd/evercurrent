from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.auth.auth0 import Auth0Claims, Auth0Verifier, InvalidTokenError
from evercurrent.db.models import Org, OrgMembership
from evercurrent.db.session import admin_session_scope, get_sessionmaker
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


def _role_from_claims(claims: Auth0Claims) -> str:
    return "admin" if "admin" in claims.roles else "member"


async def _get_or_create_org(admin: AsyncSession, claims: Auth0Claims) -> Org:
    org = (
        await admin.execute(select(Org).where(Org.auth0_org_id == claims.org_id))
    ).scalar_one_or_none()
    if org is not None:
        if claims.org_name and org.name != claims.org_name:
            org.name = claims.org_name
            await admin.commit()
            await admin.refresh(org)
        return org
    org = Org(auth0_org_id=str(claims.org_id), name=claims.org_name or str(claims.org_id))
    admin.add(org)
    try:
        await admin.commit()
    except IntegrityError:
        await admin.rollback()
        return (
            await admin.execute(select(Org).where(Org.auth0_org_id == claims.org_id))
        ).scalar_one()
    await admin.refresh(org)
    log.info("auth.org.provisioned", org_id=str(org.id), auth0_org_id=org.auth0_org_id)
    return org


async def _provision_membership(
    admin: AsyncSession,
    org: Org,
    claims: Auth0Claims,
    role: str,
) -> OrgMembership:
    """JIT provision the (org, user) membership from the verified token; sync role
    on every login so Auth0 role changes propagate."""
    membership = (
        await admin.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org.id,
                OrgMembership.auth0_user_id == claims.sub,
            ),
        )
    ).scalar_one_or_none()
    email = claims.email or ""
    name = claims.name or claims.email or claims.sub
    if membership is None:
        membership = OrgMembership(
            org_id=org.id,
            auth0_user_id=claims.sub,
            email=email,
            display_name=name,
            role=role,
        )
        admin.add(membership)
        try:
            await admin.commit()
        except IntegrityError:
            await admin.rollback()
            return (
                await admin.execute(
                    select(OrgMembership).where(
                        OrgMembership.org_id == org.id,
                        OrgMembership.auth0_user_id == claims.sub,
                    ),
                )
            ).scalar_one()
        await admin.refresh(membership)
        log.info("auth.membership.provisioned", membership_id=str(membership.id), role=role)
        return membership

    changed = False
    if membership.role != role:
        membership.role = role
        changed = True
    if email and membership.email != email:
        membership.email = email
        changed = True
    if membership.display_name != name:
        membership.display_name = name
        changed = True
    if changed:
        await admin.commit()
        await admin.refresh(membership)
    return membership


async def require_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: VerifierDep,
    session: SessionDep,
) -> CurrentUser:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    try:
        claims = await verifier.verify(creds.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    if claims.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="token has no org_id claim — log in to an organization",
        )

    role = _role_from_claims(claims)
    impersonate = request.headers.get("x-impersonate-user")
    async with admin_session_scope() as admin:
        org = await _get_or_create_org(admin, claims)
        membership = await _provision_membership(admin, org, claims, role)
        scoped_id = membership.id
        scoped_name = membership.display_name
        scoped_email = membership.email
        if impersonate and role == "admin":
            try:
                target = await admin.get(OrgMembership, uuid.UUID(impersonate))
            except ValueError:
                target = None
            if target is not None and target.org_id == org.id:
                scoped_id = target.id
                scoped_name = target.display_name
                scoped_email = target.email
        org_id = org.id

    request.state.org_id = org_id
    await set_org_context(session, org_id)

    return CurrentUser(
        org_id=org_id,
        membership_id=scoped_id,
        auth0_user_id=claims.sub,
        email=scoped_email,
        display_name=scoped_name,
        role=role,
    )


class CurrentUser:
    __slots__ = ("auth0_user_id", "display_name", "email", "membership_id", "org_id", "role")

    def __init__(
        self,
        *,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
        auth0_user_id: str,
        email: str,
        display_name: str,
        role: str = "member",
    ) -> None:
        self.org_id = org_id
        self.membership_id = membership_id
        self.auth0_user_id = auth0_user_id
        self.email = email
        self.display_name = display_name
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


CurrentUserDep = Annotated[CurrentUser, Depends(require_user)]


async def require_admin(user: CurrentUserDep) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
