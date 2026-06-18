"""Task: generate (or regenerate) one member's digest for a given day, skipping
if a fresh one already exists unless forced."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.repositories.memberships import MembershipRepository
from evercurrent.db.session import session_scope
from evercurrent.digest import repository as digest_repo
from evercurrent.digest.digest_generator import generate_digest
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.sse_publisher import publish_event
from evercurrent.tenancy.org_context import set_org_context

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
        org_id = await MembershipRepository(session).org_id_for_member(parsed_member_id)
        if org_id is None:
            log.warning(
                "digest.task.missing_membership",
                project_member_id=project_member_id,
            )
            return {
                "project_member_id": project_member_id,
                "status": "missing",
            }
        await set_org_context(session, org_id)

        project_id = await digest_repo.latest_project_id_for_org(session, org_id=org_id)

        digest = await generate_digest(
            session,
            provider,
            project_member_id=parsed_member_id,
            day_index=day_index,
            phase=phase,
            force=force,
        )
        await session.commit()

    if digest is None:
        log.info("digest.task.skipped_empty", project_member_id=project_member_id)
        return {"project_member_id": project_member_id, "status": "skipped_empty"}

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
