"""Persistence for computed scores: idempotent upserts keyed on
(project_member_id, message_id) so re-scoring a message overwrites in place."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import OrgMembership, Project, Score
from evercurrent.scoring.schemas import MessageTag, ScoreResult, ScoringMember


async def get_message_tag(session: AsyncSession, message_id: uuid.UUID) -> MessageTag | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT topic, urgency, entities, affected_roles "
                    "FROM message_tags WHERE message_id = :id",
                ),
                {"id": str(message_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return MessageTag(
        topic=row["topic"],
        urgency=row["urgency"],
        entities=list(row["entities"] or []),
        affected_roles=list(row["affected_roles"] or []),
    )


async def members_for_org(session: AsyncSession, org_id: uuid.UUID) -> list[ScoringMember]:
    rows = (
        (await session.execute(select(OrgMembership).where(OrgMembership.org_id == org_id)))
        .scalars()
        .all()
    )
    return [
        ScoringMember(
            id=m.id,
            role=m.role,
            eng_role=m.eng_role,
            owned_subsystems=list(m.owned_subsystems or []),
            topic_weights=dict(m.topic_weights or {}),
        )
        for m in rows
    ]


async def project_phase_concerns(
    session: AsyncSession,
    project_id: uuid.UUID | None,
) -> list[str]:
    stmt = (
        select(Project).where(Project.id == project_id)
        if project_id is not None
        else select(Project).limit(1)
    )
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None:
        return []
    return list((project.phase_concerns or {}).get(project.current_phase, []))


async def upsert_score(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_member_id: uuid.UUID,
    message_id: uuid.UUID,
    result: ScoreResult,
) -> None:
    stmt = (
        insert(Score)
        .values(
            org_id=org_id,
            project_member_id=project_member_id,
            message_id=message_id,
            score=result.total,
            reasons=result.breakdown,
        )
        .on_conflict_do_update(
            index_elements=["project_member_id", "message_id"],
            set_={
                "score": result.total,
                "reasons": result.breakdown,
                "computed_at": insert(Score).excluded.computed_at,
            },
        )
    )
    await session.execute(stmt)


async def bulk_upsert_scores(
    session: AsyncSession,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        return
    stmt = (
        insert(Score)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["project_member_id", "message_id"],
            set_={
                "score": insert(Score).excluded.score,
                "reasons": insert(Score).excluded.reasons,
            },
        )
    )
    await session.execute(stmt)
