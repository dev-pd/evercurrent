"""Persistence + lookup helpers for the route_message pipeline. SQL lives here;
route_message.py keeps the orchestration."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.classification.schemas import RouterDecision

log = structlog.get_logger(__name__)


async def load_raw_event(
    session: AsyncSession,
    raw_event_id: uuid.UUID,
) -> dict[str, Any] | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, org_id, source, external_id, payload "
                    "FROM raw_events WHERE id = :id",
                ),
                {"id": str(raw_event_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return dict(row)


async def upsert_message(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    external_id: str,
    channel: str | None,
    text_body: str,
    author_display_name: str,
    posted_at_epoch: float,
    thread_ts: str | None,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    inserted = await session.execute(
        text(
            "INSERT INTO messages "
            "(org_id, project_id, source, external_id, channel, text, "
            " author_display_name, posted_at) "
            "VALUES (:org_id, "
            "        (SELECT id FROM projects WHERE org_id = :org_id "
            "         ORDER BY created_at LIMIT 1), "
            "        'slack', :external_id, :channel, :text, "
            "        :author, to_timestamp(:posted_at)) "
            "ON CONFLICT (source, external_id) DO NOTHING "
            "RETURNING id, project_id",
        ),
        {
            "org_id": str(org_id),
            "external_id": external_id,
            "channel": channel,
            "text": text_body,
            "author": author_display_name,
            "posted_at": posted_at_epoch,
        },
    )
    row = inserted.mappings().first()
    if row is not None:
        message_id = uuid.UUID(str(row["id"]))
        project_id = uuid.UUID(str(row["project_id"])) if row["project_id"] else None
    else:
        existing = await session.execute(
            text(
                "SELECT id, project_id FROM messages WHERE source = 'slack' AND external_id = :ext",
            ),
            {"ext": external_id},
        )
        existing_row = existing.mappings().first()
        if existing_row is None:
            msg = f"failed to upsert or find message external_id={external_id}"
            raise RuntimeError(msg)
        message_id = uuid.UUID(str(existing_row["id"]))
        project_id = (
            uuid.UUID(str(existing_row["project_id"])) if existing_row["project_id"] else None
        )

    if thread_ts and thread_ts != external_id:
        await session.execute(
            text(
                "UPDATE messages SET thread_root_id = parent.id "
                "FROM messages parent "
                "WHERE messages.source = 'slack' "
                "  AND messages.external_id = :ext "
                "  AND parent.source = 'slack' "
                "  AND parent.external_id = :parent_ext",
            ),
            {"ext": external_id, "parent_ext": thread_ts},
        )

    return message_id, project_id


async def resolve_thread_parent_text(
    session: AsyncSession,
    *,
    thread_ts: str | None,
    own_external_id: str,
) -> str | None:
    if not thread_ts or thread_ts == own_external_id:
        return None
    row = (
        await session.execute(
            text(
                "SELECT text FROM messages WHERE source = 'slack' AND external_id = :ext",
            ),
            {"ext": thread_ts},
        )
    ).first()
    if row is None:
        return None
    return str(row[0])


async def resolve_author_role(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    slack_user_id: str | None,
) -> str:
    if not slack_user_id:
        return "member"
    row = (
        await session.execute(
            text(
                "SELECT role FROM org_memberships "
                "WHERE org_id = :org_id AND slack_user_id = :uid "
                "LIMIT 1",
            ),
            {"org_id": str(org_id), "uid": slack_user_id},
        )
    ).first()
    if row is None:
        return "member"
    return str(row[0])


async def link_author_membership(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    message_id: uuid.UUID,
    slack_user_id: str | None,
) -> str | None:
    """Link a webhook message to an already-provisioned member by Slack uid so
    the live path resolves author name/membership immediately, instead of
    leaving the raw uid until the next Sync. Returns the resolved display name,
    or None when no member exists yet (a later Sync provisions them)."""
    if not slack_user_id:
        return None
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, display_name FROM org_memberships "
                    "WHERE org_id = :org_id AND slack_user_id = :uid LIMIT 1",
                ),
                {"org_id": str(org_id), "uid": slack_user_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    await session.execute(
        text(
            "UPDATE messages SET author_membership_id = :mid, author_display_name = :name "
            "WHERE id = :msg",
        ),
        {"mid": str(row["id"]), "name": row["display_name"], "msg": str(message_id)},
    )
    return str(row["display_name"])


async def resolve_project_phase(
    session: AsyncSession,
    project_id: uuid.UUID | None,
) -> str:
    if project_id is None:
        return "unknown"
    row = (
        await session.execute(
            text("SELECT current_phase FROM projects WHERE id = :id"),
            {"id": str(project_id)},
        )
    ).first()
    if row is None:
        return "unknown"
    return str(row[0])


async def write_tag(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    message_id: uuid.UUID,
    decision: RouterDecision,
    tagged_by_model: str,
) -> None:
    await session.execute(
        text(
            "INSERT INTO message_tags "
            "(org_id, message_id, topic, urgency, entities, affected_roles, "
            " tagged_by_model) "
            "VALUES (:org_id, :message_id, :topic, :urgency, "
            "        CAST(:entities AS text[]), CAST(:affected_roles AS text[]), "
            "        :tagged_by_model) "
            "ON CONFLICT (message_id) DO UPDATE SET "
            "  topic = EXCLUDED.topic, "
            "  urgency = EXCLUDED.urgency, "
            "  entities = EXCLUDED.entities, "
            "  affected_roles = EXCLUDED.affected_roles, "
            "  tagged_by_model = EXCLUDED.tagged_by_model, "
            "  tagged_at = now()",
        ),
        {
            "org_id": str(org_id),
            "message_id": str(message_id),
            "topic": decision.topic,
            "urgency": decision.urgency,
            "entities": decision.entities,
            "affected_roles": decision.affected_roles,
            "tagged_by_model": tagged_by_model,
        },
    )
