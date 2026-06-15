"""Async Eve: run the insight agent on the worker, store it, and push it to the
UI over SSE. Keeps the user's request non-blocking (run_eve takes ~10s).

Duplicate guard is layered: recent insights are injected into Eve's goal so it
aims for novelty, and an embedding-similarity gate deterministically rejects a
new insight that is too close to an existing one (semantic dedup)."""

from __future__ import annotations

import datetime as dt
import json
import math
import uuid
from typing import Any

import structlog
from sqlalchemy import text

from evercurrent.config import Settings, get_settings
from evercurrent.db.session import session_scope
from evercurrent.eve import EveRun, run_eve
from evercurrent.eve.grounding import ground_sources
from evercurrent.rag.embedder import get_embedder
from evercurrent.realtime import publish_event
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)


def _gate(
    emitted: dict[str, Any],
    run: EveRun,
    settings: Settings,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Deterministic acceptance gate. Returns (rejection_reason or None,
    grounded_sources). Order matters: cheapest/strongest checks first."""
    grounded = ground_sources(emitted.get("sources") or [], run.evidence)
    if not run.searched:
        return "no_search", grounded
    if len(grounded) < settings.eve_min_grounded_sources:
        return "ungrounded", grounded
    confidence = float(emitted.get("confidence") or 0.0)
    if confidence < settings.eve_min_confidence:
        return "low_confidence", grounded
    return None, grounded


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
        "confidence": emitted.get("confidence"),
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


def _build_goal(recent: list[tuple[str | None, str | None]]) -> str:
    goal = (
        "Review the most recent decisions, team messages, and spec documents. "
        "Find one high-impact change or a chatter-vs-spec conflict and emit it."
    )
    if recent:
        flagged = "\n".join(f"- {t}: {(s or '')[:120]}" for t, s in recent)
        goal += (
            "\n\nALREADY FLAGGED — do NOT repeat these or minor re-wordings of them. "
            "Surface a genuinely DIFFERENT issue (a different requirement, subsystem, "
            "or conflict):\n" + flagged
        )
    return goal


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def _is_duplicate(
    payload: dict[str, Any],
    recent: list[tuple[str | None, str | None]],
) -> float:
    if not recent:
        return 0.0
    embedder = get_embedder()
    new_text = f"{payload['title']} {payload['summary']}"
    old_texts = [f"{t or ''} {s or ''}" for t, s in recent]
    vecs = await embedder.embed_documents([new_text, *old_texts])
    new_vec, old_vecs = vecs[0], vecs[1:]
    return max((_cosine(new_vec, ov) for ov in old_vecs), default=0.0)


async def generate_eve_insight(
    _ctx: dict[str, Any],
    project_id: str,
    org_id: str,
) -> dict[str, Any]:
    pid = uuid.UUID(project_id)
    oid = uuid.UUID(org_id)
    settings = get_settings()
    async with session_scope() as session:
        await set_org_context(session, oid)
        recent = [
            (r[0], r[1])
            for r in (
                await session.execute(
                    text(
                        "SELECT payload->>'title', payload->>'summary' FROM insights "
                        "WHERE org_id = :o ORDER BY created_at DESC LIMIT 8",
                    ),
                    {"o": str(oid)},
                )
            ).all()
        ]

        count_today = (
            await session.execute(
                text(
                    "SELECT count(*) FROM insights WHERE org_id = :o "
                    "AND created_at >= date_trunc('day', now())",
                ),
                {"o": str(oid)},
            )
        ).scalar_one()
        if count_today >= settings.eve_max_insights_per_day:
            publish_event(pid, "insight_failed", {"reason": "daily_cap"})
            return {"status": "daily_cap", "count": int(count_today)}

        run = await run_eve(session, project_id=pid, seed=_build_goal(recent))
        emitted = run.insight
        if emitted is None:
            publish_event(pid, "insight_failed", {"reason": "none"})
            return {"status": "no_insight"}

        reason, grounded = _gate(emitted, run, settings)
        emitted["sources"] = grounded
        if reason is not None:
            log.info(
                "eve.rejected",
                reason=reason,
                searched=run.searched,
                grounded=len(grounded),
                confidence=emitted.get("confidence"),
            )
            publish_event(pid, "insight_failed", {"reason": reason})
            return {"status": "rejected", "reason": reason}

        insight_id = str(uuid.uuid4())
        when = dt.datetime.now(dt.UTC).isoformat()
        payload = _normalize(emitted, insight_id=insight_id, when=when)

        max_sim = await _is_duplicate(payload, recent)
        if max_sim >= settings.eve_dedup_threshold:
            log.info("eve.duplicate_skipped", max_sim=round(max_sim, 3), title=payload["title"])
            publish_event(pid, "insight_failed", {"reason": "duplicate"})
            return {"status": "duplicate", "max_sim": max_sim}

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
