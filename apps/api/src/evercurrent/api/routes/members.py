from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from evercurrent.auth.deps import AdminUserDep, CurrentUserDep, SessionDep
from evercurrent.config import get_settings
from evercurrent.db.repositories.memberships import MembershipRepository
from evercurrent.domain.memberships import MemberSummary

router = APIRouter(prefix="/members", tags=["members"])


class MemberUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    eng_role: str | None = None
    owned_subsystems: list[str] | None = None


class MemberCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    display_name: str
    eng_role: str | None = None
    owned_subsystems: list[str] = []


async def _load_member(repo: MembershipRepository, membership_id: uuid.UUID) -> MemberSummary:
    member = await repo.get_summary(membership_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
    return member


@router.get("", response_model=list[MemberSummary])
async def list_members(session: SessionDep, user: CurrentUserDep) -> list[MemberSummary]:
    _ = user
    return await MembershipRepository(session).list_personas(
        bot_name=get_settings().slack_app_bot_name,
    )


@router.post("", response_model=MemberSummary, status_code=status.HTTP_201_CREATED)
async def create_member(
    body: MemberCreate,
    session: SessionDep,
    admin: AdminUserDep,
) -> MemberSummary:
    repo = MembershipRepository(session)
    new_id = await repo.create(
        org_id=admin.org_id,
        display_name=body.display_name,
        eng_role=body.eng_role,
        owned_subsystems=body.owned_subsystems,
    )
    member = await _load_member(repo, new_id)
    await session.commit()
    return member


@router.patch("/{membership_id}", response_model=MemberSummary)
async def update_member(
    membership_id: uuid.UUID,
    body: MemberUpdate,
    session: SessionDep,
    admin: AdminUserDep,
) -> MemberSummary:
    _ = admin
    repo = MembershipRepository(session)
    changed = await repo.update_fields(
        membership_id,
        eng_role=body.eng_role,
        owned_subsystems=body.owned_subsystems,
    )
    # Read inside the same transaction: committing drops the SET LOCAL org
    # context, which would make the re-read fail RLS.
    member = await _load_member(repo, membership_id)
    if changed:
        await session.commit()
    return member
