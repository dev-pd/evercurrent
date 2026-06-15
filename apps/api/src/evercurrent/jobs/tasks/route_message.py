from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.session import session_scope
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.realtime import publish_event
from evercurrent.routing import classify
from evercurrent.routing.schemas import RouterDecision
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


async def _load_raw_event(
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


def _extract_slack_event(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    event = payload.get("event")
    if isinstance(event, dict):
        return event
    # Backfill stores the bare conversations.history message (no envelope).
    if payload.get("type") == "message":
        return payload
    return None


async def _upsert_message(
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


async def _resolve_thread_parent_text(
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


async def _resolve_author_role(
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


async def _resolve_project_phase(
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


async def _write_tag(
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


def _enqueue_followups(
    *,
    message_id: uuid.UUID,
    decision: RouterDecision,
) -> None:
    from evercurrent.jobs.celery_app import celery_app

    if decision.should_create_card and decision.card_kind is not None:
        try:
            celery_app.send_task(
                "evercurrent.build_card",
                kwargs={
                    "message_id": str(message_id),
                    "kind": decision.card_kind,
                    "summary_hint": decision.card_summary or "",
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "router.build_card_enqueue_failed",
                message_id=str(message_id),
                error=str(exc),
            )

    try:
        celery_app.send_task(
            "evercurrent.score_message_for_members",
            kwargs={"message_id": str(message_id)},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "router.score_enqueue_failed",
            message_id=str(message_id),
            error=str(exc),
        )


async def _route(
    raw_event_id: uuid.UUID,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, Any]:
    provider = llm or get_provider()
    async with session_scope() as session:
        raw = await _load_raw_event(session, raw_event_id)
        if raw is None:
            log.warning("router.route.missing", raw_event_id=str(raw_event_id))
            return {"raw_event_id": str(raw_event_id), "status": "missing"}

        org_id = uuid.UUID(str(raw["org_id"]))
        await set_org_context(session, org_id)

        event = _extract_slack_event(raw["payload"])
        if event is None:
            log.warning(
                "router.route.bad_payload",
                raw_event_id=str(raw_event_id),
            )
            return {"raw_event_id": str(raw_event_id), "status": "bad_payload"}

        external_id = str(event.get("ts") or raw["external_id"])
        thread_ts_raw = event.get("thread_ts")
        thread_ts = str(thread_ts_raw) if thread_ts_raw else None
        channel = event.get("channel")
        channel_str = str(channel) if channel else None
        text_body = str(event.get("text") or "")
        slack_user_id = event.get("user")
        slack_user_str = str(slack_user_id) if slack_user_id else None
        username = event.get("username")
        author_display = (
            str(username)
            if username
            else slack_user_str or str(event.get("bot_id") or "") or "unknown"
        )
        try:
            posted_at_epoch = float(external_id)
        except ValueError:
            posted_at_epoch = 0.0

        message_id, project_id = await _upsert_message(
            session,
            org_id=org_id,
            external_id=external_id,
            channel=channel_str,
            text_body=text_body,
            author_display_name=author_display,
            posted_at_epoch=posted_at_epoch,
            thread_ts=thread_ts,
        )

        thread_parent_text = await _resolve_thread_parent_text(
            session,
            thread_ts=thread_ts,
            own_external_id=external_id,
        )
        author_role = await _resolve_author_role(
            session,
            org_id=org_id,
            slack_user_id=slack_user_str,
        )
        project_phase = await _resolve_project_phase(session, project_id)

        try:
            decision = await classify(
                llm=provider,
                message_text=text_body,
                channel=channel_str or "unknown",
                author_display_name=author_display,
                author_role=author_role,
                thread_parent_text=thread_parent_text,
                project_phase=project_phase,
            )
            tagged_by_model = "haiku"
        except Exception as exc:  # noqa: BLE001
            from evercurrent.routing.schemas import fallback_decision

            decision = fallback_decision()
            tagged_by_model = "fallback"
            log.warning(
                "router.classify.exception",
                error=str(exc),
                message_id=str(message_id),
            )

        if decision.topic is None and decision.urgency == "normal":
            tagged_by_model = "fallback"

        try:
            await _write_tag(
                session,
                org_id=org_id,
                message_id=message_id,
                decision=decision,
                tagged_by_model=tagged_by_model,
            )
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            log.warning(
                "router.write_tag_conflict",
                message_id=str(message_id),
                error=str(exc),
            )

    if project_id is not None:
        publish_event(
            project_id,
            "message_tagged",
            {
                "message_id": str(message_id),
                "topic": decision.topic,
                "urgency": decision.urgency,
                "should_create_card": decision.should_create_card,
            },
        )

    _enqueue_followups(
        message_id=message_id,
        decision=decision,
    )

    log.info(
        "router.classify",
        message_id=str(message_id),
        org_id=str(org_id),
        topic=decision.topic,
        urgency=decision.urgency,
        should_create_card=decision.should_create_card,
        confidence=decision.confidence,
    )

    return {
        "raw_event_id": str(raw_event_id),
        "status": "ok",
        "message_id": str(message_id),
        "should_create_card": decision.should_create_card,
    }


async def route_message(
    _ctx: dict[str, Any],
    raw_event_id: str,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, Any]:
    parsed = uuid.UUID(raw_event_id)
    return await _route(parsed, llm=llm)
