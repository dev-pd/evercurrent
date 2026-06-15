"""Async Eve: run the insight agent on the worker, store it, and push it to the
UI over SSE. Keeps the user's request non-blocking (run_eve takes ~10s)."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import structlog
from sqlalchemy import text

from evercurrent.db.session import session_scope
from evercurrent.eve import run_eve
from evercurrent.realtime import publish_event
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


def _normalize(emitted: dict[str, Any], *, insight_id: str, when: str) -> dict[str, Any]:
    sources = [
        {
            "kind": s.get("kind", "slack"),
            "channel": s.get("channel"),
            "author": s.get("author"),
            "snippet": s.get("snippet", ""),
            "ts": s.get("ts"),
        }
        for s in (emitted.get("sources") or [])
    ]
    return {
        "id": insight_id,
        "req_id": emitted.get("req_id") or "—",
        "title": emitted.get("title") or "Untitled insight",
        "detected_at": when,
        "summary": emitted.get("summary") or "",
        "before": emitted.get("before") or [],
        "after": emitted.get("after") or [],
        "affected_subsystems": emitted.get("affected_subsystems") or [],
        "conflicts": emitted.get("conflicts") or [],
        "sources": sources,
        "suggested_action": emitted.get("suggested_action")
        or {"label": "Review with the team", "invitees": [], "description": ""},
        "impact_summary": emitted.get("impact_summary") or {},
    }


async def generate_eve_insight(
    _ctx: dict[str, Any],
    project_id: str,
    org_id: str,
) -> dict[str, Any]:
    pid = uuid.UUID(project_id)
    oid = uuid.UUID(org_id)
    async with session_scope() as session:
        await set_org_context(session, oid)
        emitted = await run_eve(session, project_id=pid)
        if emitted is None:
            publish_event(pid, "insight_failed", {})
            return {"status": "no_insight"}

        insight_id = str(uuid.uuid4())
        when = dt.datetime.now(dt.UTC).isoformat()
        payload = _normalize(emitted, insight_id=insight_id, when=when)

        # run_eve only reads; drop its txn, re-apply org context (SET LOCAL is
        # txn-scoped) before the RLS-checked INSERT.
        await session.rollback()
        await set_org_context(session, oid)
        await session.execute(
            text("INSERT INTO insights (org_id, payload) VALUES (:org, CAST(:p AS jsonb))"),
            {"org": str(oid), "p": json.dumps(payload)},
        )
        await session.commit()

    publish_event(pid, "insight_created", {"id": insight_id, "title": payload["title"]})
    log.info("eve.insight_stored", insight_id=insight_id, title=payload["title"])
    return {"status": "ok", "id": insight_id}
