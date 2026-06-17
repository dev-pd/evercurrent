"""Current-user route: the authenticated member's profile and org branding."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.db.repositories.memberships import MembershipRepository

router = APIRouter(prefix="/me", tags=["me"])


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
    profile = await MembershipRepository(session).get_me_profile(current_user.membership_id)
    return MeResponse(
        membership_id=current_user.membership_id,
        org_id=current_user.org_id,
        org_name=profile.org_name if profile else "",
        branding=profile.branding if profile else {},
        role=profile.role if profile else "member",
        auth0_user_id=current_user.auth0_user_id,
        email=current_user.email,
        display_name=current_user.display_name,
    )
