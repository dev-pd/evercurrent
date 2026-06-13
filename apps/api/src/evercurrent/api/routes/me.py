from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import CurrentUserDep

router = APIRouter(prefix="/api/v1/me", tags=["me"])


class MeResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    membership_id: uuid.UUID
    org_id: uuid.UUID
    auth0_user_id: str
    email: str
    display_name: str


@router.get("")
async def get_me(current_user: CurrentUserDep) -> MeResponse:
    return MeResponse(
        membership_id=current_user.membership_id,
        org_id=current_user.org_id,
        auth0_user_id=current_user.auth0_user_id,
        email=current_user.email,
        display_name=current_user.display_name,
    )
