"""Regression for set_status against a real DB: resolving_message_id is a uuid
column, and the resolve UPDATE bound it as text — which crashed every
auto-resolution with `column "resolving_message_id" is of type uuid but
expression is of type text`. Unit tests mocked set_status, so only an
integration test against migrated Postgres catches it. Skips if DATABASE_URL
isn't set (CI applies `alembic upgrade head` first).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evercurrent.signals import repository as signals_repo


@pytest.mark.asyncio
async def test_set_status_resolved_stamps_resolving_message_uuid() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")

    engine = create_async_engine(url)
    org_id = uuid.uuid4()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = async_sessionmaker(bind=conn, expire_on_commit=False)()
            await session.execute(
                text("SELECT set_config('app.current_org_id', :o, true)"),
                {"o": str(org_id)},
            )
            await session.execute(
                text("INSERT INTO orgs (id, auth0_org_id, name) VALUES (:id, :a, 'test-org')"),
                {"id": str(org_id), "a": f"org_{org_id.hex[:8]}"},
            )
            msg_id = uuid.uuid4()
            await session.execute(
                text(
                    "INSERT INTO messages "
                    "(id, org_id, source, external_id, author_display_name, text, posted_at) "
                    "VALUES (:id, :org, 'slack', :ext, 'tester', 'closing this out', now())"
                ),
                {"id": str(msg_id), "org": str(org_id), "ext": str(uuid.uuid4())},
            )
            signal_id = await signals_repo.insert_signal(
                session,
                org_id=org_id,
                project_id=None,
                kind="risk",
                summary="lead-time slip",
                body="details",
                affected_subsystems=[],
                affected_roles=[],
                confidence=0.9,
                decided_at=None,
                triggering_message_id=msg_id,
            )

            flipped = await signals_repo.set_status(
                session,
                signal_id=signal_id,
                status="resolved",
                resolving_message_id=msg_id,
            )

            assert flipped is True
            row = (
                (
                    await session.execute(
                        text(
                            "SELECT status, resolving_message_id, resolved_at "
                            "FROM signals WHERE id = :id"
                        ),
                        {"id": str(signal_id)},
                    )
                )
                .mappings()
                .first()
            )
            assert row is not None
            assert row["status"] == "resolved"
            assert str(row["resolving_message_id"]) == str(msg_id)
            assert row["resolved_at"] is not None

            await trans.rollback()
            await session.close()
    finally:
        await engine.dispose()
