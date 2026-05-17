"""FastAPI dependency factories."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings, get_settings
from evercurrent.db.session import get_session as _db_session


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in _db_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_current_user_id(
    x_impersonate_user: Annotated[str | None, Header()] = None,
) -> uuid.UUID | None:
    if not x_impersonate_user:
        return None
    try:
        return uuid.UUID(x_impersonate_user)
    except ValueError:
        return None


CurrentUserId = Annotated["uuid.UUID | None", Depends(get_current_user_id)]


def get_app_settings() -> Settings:
    return get_settings()


AppSettings = Annotated[Settings, Depends(get_app_settings)]
