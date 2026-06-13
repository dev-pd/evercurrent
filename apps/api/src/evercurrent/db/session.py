from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from evercurrent.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_admin_engine: AsyncEngine | None = None
_admin_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _make_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=5,
        future=True,
    )


def _build_engine(settings: Settings) -> AsyncEngine:
    return _make_engine(settings.app_database_url or settings.database_url)


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine
    _engine = _build_engine(settings or get_settings())
    _sessionmaker = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return _engine


async def dispose_engine() -> None:
    global _engine, _sessionmaker, _admin_engine, _admin_sessionmaker
    if _engine is not None:
        await _engine.dispose()
    if _admin_engine is not None:
        await _admin_engine.dispose()
    _engine = None
    _sessionmaker = None
    _admin_engine = None
    _admin_sessionmaker = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


def _get_admin_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _admin_engine, _admin_sessionmaker
    if _admin_sessionmaker is None:
        _admin_engine = _make_engine(get_settings().database_url)
        _admin_sessionmaker = async_sessionmaker(
            bind=_admin_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _admin_sessionmaker


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as session:
        yield session


@asynccontextmanager
async def admin_session_scope() -> AsyncIterator[AsyncSession]:
    """Privileged session (DB owner) that bypasses RLS.

    Only for bootstrap + signature-verified provisioning that must operate
    across org boundaries (dev-user lookup, the Auth0 org/member webhook).
    """
    sm = _get_admin_sessionmaker()
    async with sm() as session:
        yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as session:
        yield session
