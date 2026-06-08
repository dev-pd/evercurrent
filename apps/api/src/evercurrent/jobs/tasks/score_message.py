"""Score a tagged message for every project member.

Loads the message + tags + project, fans out via the pure
`scoring.engine.score()` function, and bulk-upserts results into
`scores`. Phase 8 will wire this into the digest pipeline; for now it
runs whenever the router agent enqueues it after writing a tag.

Best-effort: missing data (no tags, no members in the org) is a no-op
that returns a `skipped` reason rather than raising — the message
ingest pipeline should never crash because scoring isn't ready.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select

from evercurrent.db import models
from evercurrent.db.session import session_scope
from evercurrent.scoring.engine import score
from evercurrent.scoring.repository import bulk_upsert_scores
from evercurrent.scoring.schemas import ScoreInput
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


async def score_message_for_members(
    _ctx: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    msg_uuid = uuid.UUID(message_id)
    async with session_scope() as session:
        msg = (
            await session.execute(
                select(models.Message).where(models.Message.id == msg_uuid),
            )
        ).scalar_one_or_none()
        if msg is None:
            log.info("scoring.skipped", reason="message_missing", message_id=message_id)
            return {"scored": 0, "reason": "message_missing"}

        org_id = getattr(msg, "org_id", None)
        if org_id is None:
            log.info("scoring.skipped", reason="no_org_id", message_id=message_id)
            return {"scored": 0, "reason": "no_org_id"}
        await set_org_context(session, org_id)

        tag = (
            await session.execute(
                select(models.MessageTag).where(models.MessageTag.message_id == msg_uuid),
            )
        ).scalar_one_or_none()
        if tag is None:
            log.info("scoring.skipped", reason="no_tag", message_id=message_id)
            return {"scored": 0, "reason": "no_tag"}

        memberships = (
            await session.execute(
                select(models.OrgMembership).where(models.OrgMembership.org_id == org_id),
            )
        ).scalars().all()
        if not memberships:
            return {"scored": 0, "reason": "no_members"}

        rows: list[dict[str, object]] = []
        for m in memberships:
            inp = ScoreInput(
                member_role=getattr(m, "role", "member"),
                owned_subsystems=[],
                topic_weights={},
                author_role="unknown",
                message_topic=getattr(tag, "topic", None),
                message_entities=list(getattr(tag, "entities", []) or []),
                message_affected_roles=list(getattr(tag, "affected_roles", []) or []),
                message_urgency=getattr(tag, "urgency", None),
                phase_concerns=[],
            )
            result = score(inp)
            rows.append(
                {
                    "org_id": org_id,
                    "project_member_id": m.id,
                    "message_id": msg_uuid,
                    "score": result.total,
                    "reasons": result.breakdown,
                },
            )

        await bulk_upsert_scores(session, rows)
        await session.commit()
        return {"scored": len(rows)}
