"""User routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from evercurrent.api.deps import SessionDep
from evercurrent.api.schemas import UserResponse
from evercurrent.db.repositories import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    session: SessionDep,
    project_id: Annotated[uuid.UUID, Query()],
) -> list[UserResponse]:
    users = await UserRepository(session).list_for_project(project_id)
    return [UserResponse.model_validate(u.model_dump()) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, session: SessionDep) -> UserResponse:
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return UserResponse.model_validate(user.model_dump())
