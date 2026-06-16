from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ProvisioningRepository:
    """SQL for provisioning Slack authors into org_memberships and back-linking
    their messages. Orchestration (Slack lookups, persona mapping) stays in the
    connectors route."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def unprovisioned_author_names(self, *, org_id: uuid.UUID, bot_name: str) -> list[str]:
        rows = (
            (
                await self._s.execute(
                    text(
                        "SELECT DISTINCT author_display_name FROM messages "
                        "WHERE org_id = :o AND author_membership_id IS NULL "
                        "AND author_display_name NOT IN ('unknown', :bot)",
                    ),
                    {"o": str(org_id), "bot": bot_name},
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def find_member_by_slack_uid(
        self,
        *,
        org_id: uuid.UUID,
        slack_uid: str,
    ) -> uuid.UUID | None:
        row = (
            await self._s.execute(
                text("SELECT id FROM org_memberships WHERE org_id = :o AND slack_user_id = :s"),
                {"o": str(org_id), "s": slack_uid},
            )
        ).scalar_one_or_none()
        return uuid.UUID(str(row)) if row is not None else None

    async def create_slack_member(
        self,
        *,
        org_id: uuid.UUID,
        slack_uid: str,
        name: str,
        eng_role: str | None,
        owned_subsystems: list[str],
    ) -> uuid.UUID:
        row = (
            await self._s.execute(
                text(
                    "INSERT INTO org_memberships "
                    "(org_id, auth0_user_id, slack_user_id, display_name, email, "
                    " role, eng_role, owned_subsystems) "
                    "VALUES (:o, :sub, :s, :n, '', 'member', :er, "
                    "        CAST(:sub_arr AS text[])) RETURNING id",
                ),
                {
                    "o": str(org_id),
                    "sub": f"slack:{slack_uid}",
                    "s": slack_uid,
                    "n": name,
                    "er": eng_role,
                    "sub_arr": list(owned_subsystems),
                },
            )
        ).scalar_one()
        return uuid.UUID(str(row))

    async def link_messages_to_member(
        self,
        *,
        org_id: uuid.UUID,
        slack_uid: str,
        member_id: uuid.UUID,
        name: str,
    ) -> None:
        await self._s.execute(
            text(
                "UPDATE messages SET author_membership_id = :mid, author_display_name = :n "
                "WHERE org_id = :o AND author_display_name = :s",
            ),
            {"mid": str(member_id), "n": name, "o": str(org_id), "s": slack_uid},
        )
