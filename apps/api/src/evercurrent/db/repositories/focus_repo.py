from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class FocusInputs:
    eng_role: str | None
    owned_subsystems: list[str] = field(default_factory=list)
    topic_weights: dict[str, float] = field(default_factory=dict)


class FocusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def load_inputs(self, membership_id: str) -> FocusInputs | None:
        member = (
            (
                await self._s.execute(
                    text(
                        "SELECT eng_role, owned_subsystems, topic_weights "
                        "FROM org_memberships WHERE id = :id",
                    ),
                    {"id": membership_id},
                )
            )
            .mappings()
            .first()
        )
        if member is None:
            return None
        return FocusInputs(
            eng_role=member["eng_role"],
            owned_subsystems=list(member["owned_subsystems"] or []),
            topic_weights=dict(member["topic_weights"] or {}),
        )

    async def phase_concerns(self) -> list[str]:
        project = (
            (
                await self._s.execute(
                    text("SELECT current_phase, phase_concerns FROM projects LIMIT 1"),
                )
            )
            .mappings()
            .first()
        )
        if project is None:
            return []
        return list((project["phase_concerns"] or {}).get(project["current_phase"], []))

    async def get_topic_weights(self, membership_id: str) -> dict[str, float]:
        row = (
            (
                await self._s.execute(
                    text("SELECT topic_weights FROM org_memberships WHERE id = :id"),
                    {"id": membership_id},
                )
            )
            .mappings()
            .first()
        )
        return dict(row["topic_weights"] or {}) if row else {}

    async def set_topic_weights(self, membership_id: str, weights: dict[str, float]) -> None:
        await self._s.execute(
            text("UPDATE org_memberships SET topic_weights = CAST(:w AS jsonb) WHERE id = :id"),
            {"w": json.dumps(weights), "id": membership_id},
        )
