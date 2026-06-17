from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError

from evercurrent.classification import classify
from evercurrent.classification.schemas import ClassificationResult
from evercurrent.db.session import session_scope
from evercurrent.jobs.tasks.route_message_db import (
    link_author_membership,
    load_raw_event,
    resolve_author_role,
    resolve_project_phase,
    resolve_thread_parent_text,
    upsert_message,
    write_tag,
)
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.sse_publisher import publish_event
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


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


def _enqueue_followups(
    *,
    message_id: uuid.UUID,
    decision: ClassificationResult,
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
        raw = await load_raw_event(session, raw_event_id)
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

        message_id, project_id = await upsert_message(
            session,
            org_id=org_id,
            external_id=external_id,
            channel=channel_str,
            text_body=text_body,
            author_display_name=author_display,
            posted_at_epoch=posted_at_epoch,
            thread_ts=thread_ts,
        )

        await link_author_membership(
            session,
            org_id=org_id,
            message_id=message_id,
            slack_user_id=slack_user_str,
        )

        thread_parent_text = await resolve_thread_parent_text(
            session,
            thread_ts=thread_ts,
            own_external_id=external_id,
        )
        author_role = await resolve_author_role(
            session,
            org_id=org_id,
            slack_user_id=slack_user_str,
        )
        project_phase = await resolve_project_phase(session, project_id)

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
            from evercurrent.classification.schemas import fallback_classification

            decision = fallback_classification()
            tagged_by_model = "fallback"
            log.warning(
                "router.classify.exception",
                error=str(exc),
                message_id=str(message_id),
            )

        if decision.topic is None and decision.urgency == "normal":
            tagged_by_model = "fallback"

        try:
            await write_tag(
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
