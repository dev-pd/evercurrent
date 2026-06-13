from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.auth.deps import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/v1/me", tags=["me"])


class MeResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    membership_id: uuid.UUID
    org_id: uuid.UUID
    org_name: str
    branding: dict[str, Any]
    role: str
    auth0_user_id: str
    email: str
    display_name: str


@router.get("")
async def get_me(current_user: CurrentUserDep, session: SessionDep) -> MeResponse:
    row = (
        await session.execute(
            text(
                "SELECT o.name, o.branding, m.role "
                "FROM orgs o JOIN org_memberships m ON m.org_id = o.id "
                "WHERE m.id = :mid",
            ),
            {"mid": str(current_user.membership_id)},
        )
    ).first()
    return MeResponse(
        membership_id=current_user.membership_id,
        org_id=current_user.org_id,
        org_name=str(row[0]) if row else "",
        branding=dict(row[1]) if row and row[1] else {},
        role=str(row[2]) if row else "member",
        auth0_user_id=current_user.auth0_user_id,
        email=current_user.email,
        display_name=current_user.display_name,
    )
