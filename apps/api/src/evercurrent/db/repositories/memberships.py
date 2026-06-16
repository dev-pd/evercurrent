from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.domain.memberships import MemberSummary, MeProfile


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_summary(self, membership_id: uuid.UUID) -> MemberSummary | None:
        row = (
            (
                await self._s.execute(
                    text(
                        "SELECT id, display_name, eng_role, owned_subsystems "
                        "FROM org_memberships WHERE id = :id",
                    ),
                    {"id": str(membership_id)},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return MemberSummary(
            id=row["id"],
            display_name=row["display_name"],
            eng_role=row["eng_role"],
            owned_subsystems=list(row["owned_subsystems"] or []),
        )

    async def list_personas(self, *, bot_name: str) -> list[MemberSummary]:
        rows = (
            (
                await self._s.execute(
                    text(
                        "SELECT id, display_name, eng_role, owned_subsystems "
                        "FROM org_memberships "
                        "WHERE role <> 'admin' AND display_name <> :bot "
                        "ORDER BY eng_role NULLS LAST, display_name",
                    ),
                    {"bot": bot_name},
                )
            )
            .mappings()
            .all()
        )
        return [
            MemberSummary(
                id=r["id"],
                display_name=r["display_name"],
                eng_role=r["eng_role"],
                owned_subsystems=list(r["owned_subsystems"] or []),
            )
            for r in rows
        ]

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        display_name: str,
        eng_role: str | None,
        owned_subsystems: list[str],
    ) -> uuid.UUID:
        new_id = uuid.uuid4()
        await self._s.execute(
            text(
                "INSERT INTO org_memberships "
                "(id, org_id, auth0_user_id, display_name, email, role, eng_role, "
                "owned_subsystems) "
                "VALUES (:id, :org, :sub, :name, '', 'member', :role, CAST(:subs AS text[]))",
            ),
            {
                "id": str(new_id),
                "org": str(org_id),
                "sub": f"persona:{new_id}",
                "name": display_name,
                "role": eng_role,
                "subs": owned_subsystems,
            },
        )
        return new_id

    async def update_fields(
        self,
        membership_id: uuid.UUID,
        *,
        eng_role: str | None,
        owned_subsystems: list[str] | None,
    ) -> bool:
        sets: list[str] = []
        params: dict[str, object] = {"id": str(membership_id)}
        if eng_role is not None:
            sets.append("eng_role = :eng_role")
            params["eng_role"] = eng_role
        if owned_subsystems is not None:
            sets.append("owned_subsystems = CAST(:subs AS text[])")
            params["subs"] = owned_subsystems
        if not sets:
            return False
        await self._s.execute(
            text(f"UPDATE org_memberships SET {', '.join(sets)} WHERE id = :id"),
            params,
        )
        return True

    async def bump_topic_weight(
        self,
        membership_id: uuid.UUID,
        *,
        topic: str,
        delta: float,
    ) -> float | None:
        result = await self._s.execute(
            text(
                "UPDATE org_memberships "
                "SET topic_weights = COALESCE(topic_weights, '{}'::jsonb) "
                "  || jsonb_build_object(:topic, "
                "       COALESCE("
                "         (topic_weights ->> :topic)::float, 0.0"
                "       ) + :delta) "
                "WHERE id = :id "
                "RETURNING (topic_weights ->> :topic)::float",
            ),
            {"id": str(membership_id), "topic": topic, "delta": delta},
        )
        row = result.first()
        if row is None or row[0] is None:
            return None
        return float(row[0])

    async def get_me_profile(self, membership_id: uuid.UUID) -> MeProfile | None:
        row = (
            await self._s.execute(
                text(
                    "SELECT o.name, o.branding, m.role "
                    "FROM orgs o JOIN org_memberships m ON m.org_id = o.id "
                    "WHERE m.id = :mid",
                ),
                {"mid": str(membership_id)},
            )
        ).first()
        if row is None:
            return None
        return MeProfile(
            org_name=str(row[0]),
            branding=dict(row[1]) if row[1] else {},
            role=str(row[2]),
        )
