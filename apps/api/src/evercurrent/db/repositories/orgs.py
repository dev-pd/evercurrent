"""SQL for the org directory: create/delete orgs and add/remove members in
response to Auth0 organization webhook events. Idempotent on auth0 ids.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import Org, OrgMembership


class OrgDirectoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _org_by_auth0(self, auth0_org_id: str) -> Org | None:
        return (
            await self._s.execute(select(Org).where(Org.auth0_org_id == auth0_org_id))
        ).scalar_one_or_none()

    async def create_org_if_missing(self, *, auth0_org_id: str, name: str) -> None:
        if await self._org_by_auth0(auth0_org_id) is None:
            self._s.add(Org(auth0_org_id=auth0_org_id, name=name))

    async def delete_org(self, *, auth0_org_id: str) -> None:
        org = await self._org_by_auth0(auth0_org_id)
        if org is not None:
            await self._s.delete(org)

    async def add_member(
        self,
        *,
        auth0_org_id: str,
        auth0_user_id: str,
        display_name: str,
        email: str,
    ) -> None:
        org = await self._org_by_auth0(auth0_org_id)
        if org is None:
            org = Org(auth0_org_id=auth0_org_id, name=auth0_org_id)
            self._s.add(org)
            await self._s.flush()
        existing = (
            await self._s.execute(
                select(OrgMembership).where(
                    OrgMembership.org_id == org.id,
                    OrgMembership.auth0_user_id == auth0_user_id,
                ),
            )
        ).scalar_one_or_none()
        if existing is None:
            self._s.add(
                OrgMembership(
                    org_id=org.id,
                    auth0_user_id=auth0_user_id,
                    display_name=display_name,
                    email=email,
                ),
            )

    async def remove_member(self, *, auth0_org_id: str, auth0_user_id: str) -> None:
        org = await self._org_by_auth0(auth0_org_id)
        if org is None:
            return
        membership = (
            await self._s.execute(
                select(OrgMembership).where(
                    OrgMembership.org_id == org.id,
                    OrgMembership.auth0_user_id == auth0_user_id,
                ),
            )
        ).scalar_one_or_none()
        if membership is not None:
            await self._s.delete(membership)
