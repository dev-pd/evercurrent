from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from evercurrent.auth.deps import AdminUserDep, CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/v1/members", tags=["members"])


class MemberSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    display_name: str
    eng_role: str | None
    owned_subsystems: list[str]


class MemberUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    eng_role: str | None = None
    owned_subsystems: list[str] | None = None


class MemberCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    display_name: str
    eng_role: str | None = None
    owned_subsystems: list[str] = []


async def _load_member(session: SessionDep, membership_id: uuid.UUID) -> MemberSummary:
    row = (
        (
            await session.execute(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
    return MemberSummary(
        id=row["id"],
        display_name=row["display_name"],
        eng_role=row["eng_role"],
        owned_subsystems=list(row["owned_subsystems"] or []),
    )


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


@router.post("", response_model=MemberSummary, status_code=status.HTTP_201_CREATED)
async def create_member(
    body: MemberCreate,
    session: SessionDep,
    admin: AdminUserDep,
) -> MemberSummary:
    new_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO org_memberships "
            "(id, org_id, auth0_user_id, display_name, email, role, eng_role, owned_subsystems) "
            "VALUES (:id, :org, :sub, :name, '', 'member', :role, CAST(:subs AS text[]))",
        ),
        {
            "id": str(new_id),
            "org": str(admin.org_id),
            "sub": f"persona:{new_id}",
            "name": body.display_name,
            "role": body.eng_role,
            "subs": body.owned_subsystems,
        },
    )
    member = await _load_member(session, new_id)
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
    sets: list[str] = []
    params: dict[str, object] = {"id": str(membership_id)}
    if body.eng_role is not None:
        sets.append("eng_role = :eng_role")
        params["eng_role"] = body.eng_role
    if body.owned_subsystems is not None:
        sets.append("owned_subsystems = CAST(:subs AS text[])")
        params["subs"] = body.owned_subsystems
    if sets:
        await session.execute(
            text(f"UPDATE org_memberships SET {', '.join(sets)} WHERE id = :id"),
            params,
        )
    # Read inside the same transaction: committing drops the SET LOCAL org
    # context, which would make the re-read fail RLS.
    member = await _load_member(session, membership_id)
    if sets:
        await session.commit()
    return member
