"""Bootstrap a demo: provision personas + ingest real Slack history.

Run inside the api container with the bot token in env:

    docker compose exec -e SLACK_DEMO_BOT_TOKEN="$TOK" api \
        python -m evercurrent.scripts.bootstrap_demo

Provisions a project + persona members (eng role + owned subsystems), then
pulls each hardware channel's history via the Slack Web API and pushes every
message through the REAL pipeline (raw_events -> evercurrent.route_message ->
tag + score + card). Digests are generated in a second pass once scoring has
settled (see `bootstrap_digests`). Idempotent: raw_events dedupe on
(source, external_id); members upsert on (org_id, auth0_user_id).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import uuid
from typing import Any

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from evercurrent.db import models
from evercurrent.db.session import session_scope
from evercurrent.jobs.celery_app import celery_app
from evercurrent.tenancy.rls import set_org_context

log = structlog.get_logger(__name__)

# Bot is a member of these hardware channels (id -> name).
CHANNELS: dict[str, str] = {
    "C0B8ZNVJW8Z": "mech-design",
    "C0B90DNP34H": "electrical",
    "C0B8S7L1JNP": "firmware",
    "C0B8ZNRP8KB": "qa-testing",
    "C0B8XTSFL58": "supply-chain",
    "C0B92789JTE": "manufacturing",
    "C0B9ST0DA1W": "compliance",
    "C0B8UGB256H": "general",
}

# Persona members: (display_name, eng_role, owned_subsystems, org_role).
PERSONAS: list[tuple[str, str, list[str], str]] = [
    ("Sarah Chen", "mechanical", ["chassis"], "admin"),
    ("Dan Okafor", "electrical", ["power"], "member"),
    ("Priya Iyer", "firmware", ["firmware"], "member"),
    ("Lin Park", "qa", ["qa"], "member"),
    ("Raj Mehta", "supply_chain", ["supply_chain"], "member"),
    ("Mei Tanaka", "manufacturing", ["manufacturing"], "member"),
]

PHASE_CONCERNS: dict[str, list[str]] = {
    "EVT": ["bring-up", "schematic", "first-boot", "feasibility"],
    "DVT": ["thermal", "reliability", "test", "tolerance", "yield", "design-freeze"],
    "PVT": ["yield", "process", "supplier", "ramp"],
    "MP": ["cost", "supplier", "throughput", "quality"],
}
CURRENT_PHASE = "DVT"
CURRENT_DAY = 42


async def _provision(session: Any, org_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Create the project + persona members. Returns {display_name: member_id}."""
    await set_org_context(session, org_id)

    # Project ORM model lacks org_id (table has it + RLS) -> use raw SQL.
    await session.execute(
        text(
            "INSERT INTO projects "
            "(name, current_phase, current_day, start_date, phase_concerns, "
            " milestones, org_id) "
            "VALUES (:name, :phase, :day, :start, CAST(:concerns AS jsonb), "
            " '[]'::jsonb, :org) "
            "ON CONFLICT (name) DO UPDATE SET "
            "current_phase = EXCLUDED.current_phase, "
            "current_day = EXCLUDED.current_day, "
            "phase_concerns = EXCLUDED.phase_concerns"
        ),
        {
            "name": "Atlas",
            "phase": CURRENT_PHASE,
            "day": CURRENT_DAY,
            "start": dt.datetime.now(tz=dt.UTC).date() - dt.timedelta(days=CURRENT_DAY),
            "concerns": json.dumps(PHASE_CONCERNS),
            "org": str(org_id),
        },
    )

    members: dict[str, uuid.UUID] = {}
    for name, eng_role, subsystems, org_role in PERSONAS:
        auth0_id = f"persona|{name.lower().replace(' ', '-')}"
        stmt = (
            pg_insert(models.OrgMembership)
            .values(
                org_id=org_id,
                auth0_user_id=auth0_id,
                display_name=name,
                email=f"{auth0_id.split('|')[1]}@evercurrent.local",
                role=org_role,
                eng_role=eng_role,
                owned_subsystems=subsystems,
                topic_weights={},
                timezone="America/Los_Angeles",
            )
            .on_conflict_do_update(
                index_elements=["org_id", "auth0_user_id"],
                set_={
                    "eng_role": eng_role,
                    "owned_subsystems": subsystems,
                    "role": org_role,
                },
            )
            .returning(models.OrgMembership.id)
        )
        member_id = (await session.execute(stmt)).scalar_one()
        members[name] = member_id

    await session.commit()
    return members


async def _slack_history(
    client: httpx.AsyncClient, token: str, channel: str
) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(10):  # cap pagination
        params: dict[str, str] = {"channel": channel, "limit": "200"}
        if cursor:
            params["cursor"] = cursor
        r = await client.get(
            "https://slack.com/api/conversations.history",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        if not data.get("ok"):
            log.warning("slack.history.err", channel=channel, error=data.get("error"))
            break
        msgs.extend(m for m in data.get("messages", []) if m.get("type") == "message")
        cursor = data.get("response_metadata", {}).get("next_cursor") or None
        if not cursor:
            break
    return msgs


async def _ingest(session: Any, org_id: uuid.UUID, token: str) -> int:
    await set_org_context(session, org_id)
    enqueued = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for channel_id, channel_name in CHANNELS.items():
            history = await _slack_history(client, token, channel_id)
            for m in history:
                ts = str(m.get("ts"))
                payload = {
                    "team_id": "T0B8VT6SCJD",
                    "event": {
                        "type": "message",
                        "ts": ts,
                        "channel": channel_id,
                        "text": m.get("text", ""),
                        "user": m.get("user") or m.get("bot_id") or "unknown",
                        **({"thread_ts": m["thread_ts"]} if m.get("thread_ts") else {}),
                    },
                }
                stmt = (
                    pg_insert(models.RawEvent)
                    .values(
                        org_id=org_id,
                        source="slack",
                        external_id=ts,
                        payload=payload,
                    )
                    .on_conflict_do_nothing(index_elements=["source", "external_id"])
                    .returning(models.RawEvent.id)
                )
                raw_id = (await session.execute(stmt)).scalar_one_or_none()
                if raw_id is None:
                    continue
                await session.commit()
                celery_app.send_task("evercurrent.route_message", args=[str(raw_id)])
                enqueued += 1
            log.info("ingest.channel", channel=channel_name, count=len(history))
    return enqueued


async def main() -> None:
    token = os.environ.get("SLACK_DEMO_BOT_TOKEN")
    if not token:
        raise SystemExit("SLACK_DEMO_BOT_TOKEN not in env")
    async with session_scope() as session:
        org = (await session.execute(select(models.Org).limit(1))).scalar_one_or_none()
        if org is None:
            raise SystemExit("no org provisioned")
        org_id = org.id
        members = await _provision(session, org_id)
        log.info("provisioned", members={k: str(v) for k, v in members.items()})
    async with session_scope() as session:
        enqueued = await _ingest(session, org_id, token)
    log.info("ingest.done", enqueued=enqueued)
    print(f"OK provisioned {len(members)} members, enqueued {enqueued} messages")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
