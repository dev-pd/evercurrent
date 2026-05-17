"""FastAPI dependency factories.

`get_session` yields an AsyncSession scoped to the request.
`get_arq_pool` yields a singleton Redis pool used to enqueue tasks.
`get_current_user_id` reads the `X-Impersonate-User` header so the
frontend dropdown drives the personalisation.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings, get_settings
from evercurrent.db.session import get_session as _db_session


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in _db_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_arq_pool(request: Request) -> ArqRedis:
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        settings: Settings = request.app.state.settings
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        request.app.state.arq_pool = pool
    return pool


ArqPool = Annotated[ArqRedis, Depends(get_arq_pool)]


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
