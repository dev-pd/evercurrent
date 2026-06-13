from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import text

from evercurrent.cards.builder import build_card as build_card_impl
from evercurrent.db.session import session_scope
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.realtime import publish_event
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


async def _load_message_org(
    raw_message_id: uuid.UUID,
) -> uuid.UUID | None:
    async with session_scope() as session:
        row = (
            await session.execute(
                text("SELECT org_id FROM messages WHERE id = :id"),
                {"id": str(raw_message_id)},
            )
        ).first()
        if row is None:
            return None
        return uuid.UUID(str(row[0]))


async def build_card(
    _ctx: dict[str, Any],
    message_id: str,
    kind: str,
    summary_hint: str,
    *,
    llm: LLMProvider | None = None,
) -> dict[str, Any]:
    parsed_message_id = uuid.UUID(message_id)
    org_id = await _load_message_org(parsed_message_id)
    if org_id is None:
        log.warning(
            "cards.build_card.missing_message",
            message_id=message_id,
        )
        return {"message_id": message_id, "status": "missing"}

    provider = llm or get_provider()

    async with session_scope() as session:
        await set_org_context(session, org_id)
        result = await build_card_impl(
            session,
            provider,
            message_id=parsed_message_id,
            kind=kind,
            summary_hint=summary_hint,
        )
        await session.commit()

    publish_event(
        org_id,
        "card_created",
        {
            "card_id": str(result["card_id"]),
            "kind": result.get("kind", kind),
            "summary": result.get("summary", summary_hint),
            "project_id": (str(result["project_id"]) if result.get("project_id") else None),
            "existing": bool(result.get("existing", False)),
        },
    )

    return {
        "message_id": message_id,
        "card_id": str(result["card_id"]),
        "existing": bool(result.get("existing", False)),
    }
