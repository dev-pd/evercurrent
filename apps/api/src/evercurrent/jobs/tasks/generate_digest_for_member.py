"""Task: generate (or regenerate) one member's digest for a given day, skipping
if a fresh one already exists unless forced."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.session import session_scope
from evercurrent.digest.digest_generator import generate_digest
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.sse_publisher import publish_event
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

        project_row = (
            await session.execute(
                sql_text("SELECT id FROM projects WHERE org_id = :org LIMIT 1"),
                {"org": str(org_id)},
            )
        ).first()
        project_id = uuid.UUID(str(project_row[0])) if project_row else None

        digest = await generate_digest(
            session,
            provider,
            project_member_id=parsed_member_id,
            day_index=day_index,
            phase=phase,
            force=force,
        )
        await session.commit()

    if project_id is not None:
        publish_event(
            project_id,
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
