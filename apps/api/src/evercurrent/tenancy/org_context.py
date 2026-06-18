"""Row-level-security tenant context: sets `app.current_org_id` for the
transaction so Postgres RLS policies filter every query to the current org."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_org_context(session: AsyncSession, org_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_org_context(:id)"),
        {"id": str(org_id)},
    )


async def clear_org_context(session: AsyncSession) -> None:
    await session.execute(text("SELECT clear_org_context()"))
