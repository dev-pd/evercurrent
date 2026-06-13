from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.auth.deps import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/v1/members", tags=["members"])


class MemberSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    display_name: str
    eng_role: str | None
    owned_subsystems: list[str]


@router.get("", response_model=list[MemberSummary])
async def list_members(session: SessionDep, user: CurrentUserDep) -> list[MemberSummary]:
    _ = user
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id, display_name, eng_role, owned_subsystems "
                    "FROM org_memberships ORDER BY eng_role NULLS LAST, display_name",
                ),
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
