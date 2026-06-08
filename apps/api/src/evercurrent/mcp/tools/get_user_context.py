"""get_user_context tool.

Given an `org_memberships.id`, returns the member's role and (best
effort) their owned subsystems + topic weights. The new `org_memberships`
table doesn't carry `owned_subsystems` or `topic_weights` yet; those
live on the legacy `users` table, joined via `slack_user_id` (preferred)
or `email`. If no `users` row matches, the lists/maps come back empty.
"""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.mcp.schemas import UserContext

log = structlog.get_logger(__name__)

_SQL = text(
    """
    SELECT
        om.id AS membership_id,
        om.display_name AS display_name,
        om.role AS role,
        om.slack_user_id AS slack_user_id,
        om.email AS email,
        u.owned_subsystems AS owned_subsystems,
        u.topic_weights AS topic_weights
    FROM org_memberships om
    LEFT JOIN users u
        ON (om.slack_user_id IS NOT NULL AND om.slack_user_id = u.username)
        OR (om.email IS NOT NULL AND om.email <> '' AND om.email = u.username)
    WHERE om.id = :membership_id
    LIMIT 1
    """,
).bindparams(bindparam("membership_id"))


def _coerce_topic_weights(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
        elif isinstance(v, str):
            try:
                out[k] = float(v)
            except ValueError:
                continue
    return out


async def get_user_context(
    session: AsyncSession,
    *,
    membership_id: uuid.UUID,
) -> UserContext | None:
    """Return profile context for the given membership, or None if unknown."""
    start = time.perf_counter()

    row = (
        await session.execute(_SQL, {"membership_id": membership_id})
    ).mappings().first()

    if row is None:
        log.info(
            "mcp.tool_call",
            tool_name="get_user_context",
            membership_id=str(membership_id),
            result_count=0,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return None

    raw_subs = row["owned_subsystems"]
    owned_subsystems = [s for s in (raw_subs or []) if isinstance(s, str)]
    topic_weights = _coerce_topic_weights(row["topic_weights"])

    out = UserContext(
        membership_id=row["membership_id"],
        display_name=row["display_name"],
        role=row["role"],
        owned_subsystems=owned_subsystems,
        topic_weights=topic_weights,
    )

    duration_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "mcp.tool_call",
        tool_name="get_user_context",
        membership_id=str(membership_id),
        result_count=1,
        duration_ms=duration_ms,
    )
    return out
