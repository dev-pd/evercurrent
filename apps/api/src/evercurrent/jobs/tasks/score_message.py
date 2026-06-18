"""Task: score a tagged message against every project member and bulk-upsert the
per-member relevance scores."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.db.repositories.messages import MessageRepository
from evercurrent.db.session import session_scope
from evercurrent.scoring import repository as scoring_repo
from evercurrent.scoring.relevance import score
from evercurrent.scoring.schemas import ScoreInput
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


async def score_message_for_members(
    _ctx: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    msg_uuid = uuid.UUID(message_id)
    async with session_scope() as session:
        msg = await MessageRepository(session).get(msg_uuid)
        if msg is None:
            log.info("scoring.skipped", reason="message_missing", message_id=message_id)
            return {"scored": 0, "reason": "message_missing"}

        org_id = msg["org_id"]
        if org_id is None:
            log.info("scoring.skipped", reason="no_org_id", message_id=message_id)
            return {"scored": 0, "reason": "no_org_id"}
        await set_org_context(session, org_id)

        tag = await scoring_repo.get_message_tag(session, msg_uuid)
        if tag is None:
            log.info("scoring.skipped", reason="no_tag", message_id=message_id)
            return {"scored": 0, "reason": "no_tag"}

        memberships = await scoring_repo.members_for_org(session, org_id)
        if not memberships:
            return {"scored": 0, "reason": "no_members"}

        phase_concerns = await scoring_repo.project_phase_concerns(session, msg["project_id"])

        author_role = "unknown"
        author_mid = msg["author_membership_id"]
        if author_mid is not None:
            author = next((mm for mm in memberships if mm.id == author_mid), None)
            if author is not None:
                author_role = author.eng_role or author.role

        rows: list[dict[str, object]] = []
        for m in memberships:
            inp = ScoreInput(
                member_role=(m.eng_role or m.role),
                owned_subsystems=list(m.owned_subsystems),
                topic_weights=dict(m.topic_weights),
                author_role=author_role,
                message_topic=tag.topic,
                message_entities=list(tag.entities),
                message_affected_roles=list(tag.affected_roles),
                message_urgency=tag.urgency,
                phase_concerns=phase_concerns,
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

        await scoring_repo.bulk_upsert_scores(session, rows)
        await session.commit()
        return {"scored": len(rows)}
