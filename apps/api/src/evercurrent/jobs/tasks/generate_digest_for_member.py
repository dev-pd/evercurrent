"""Per-member digest generation task.

Wraps the async `digest.agent.generate_digest` so Celery can invoke it.
Publishes the `digest_ready` SSE event after commit so the dashboard
sees the row exactly when it's queryable.

Idempotent: a retry that lands after the row was written returns the
existing digest without a Sonnet roundtrip.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.session import session_scope
from evercurrent.digest.agent import generate_digest
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.realtime import publish_event
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


async def generate_digest_for_member(
    _ctx: dict[str, Any],
    project_member_id: str,
    day_index: int,
    phase: str,
    force: bool = False,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, Any]:
    """Generate a digest for one (member, day_index), publishing SSE on success."""
    parsed_member_id = uuid.UUID(project_member_id)
    provider = llm or get_provider()

    async with session_scope() as session:
        from sqlalchemy import text as sql_text

        org_row = (
            await session.execute(
                sql_text(
                    "SELECT org_id FROM org_memberships WHERE id = :id",
                ),
                {"id": project_member_id},
            )
        ).first()
        if org_row is None:
            log.warning(
                "digest.task.missing_membership",
                project_member_id=project_member_id,
            )
            return {
                "project_member_id": project_member_id,
                "status": "missing",
            }
        org_id = uuid.UUID(str(org_row[0]))
        await set_org_context(session, org_id)

        digest = await generate_digest(
            session,
            provider,
            project_member_id=parsed_member_id,
            day_index=day_index,
            phase=phase,
            force=force,
        )
        await session.commit()

    publish_event(
        org_id,
        "digest_ready",
        {
            "digest_id": str(digest.id),
            "project_member_id": project_member_id,
            "day_index": digest.day_index,
        },
    )

    return {
        "digest_id": str(digest.id),
        "project_member_id": project_member_id,
        "day_index": digest.day_index,
    }
