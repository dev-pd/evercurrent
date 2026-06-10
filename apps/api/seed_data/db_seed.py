"""Seed the EverCurrent database directly with the hardware-team demo corpus.

Run from inside the api container:

    docker compose exec api python /app/seed_data/db_seed.py

Bypasses the Slack → webhook → ingestion path so the demo works without
socket-mode listeners or public webhook URLs. The Slack workspace can
still hold the same messages (via `make slack-seed`) for visual realism.

Idempotent: keyed on project name + user username + channel name + message
text; re-running is a no-op.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
import uuid
from pathlib import Path
from typing import Final

import structlog
from sqlalchemy import text

# Allow running this file as a script: add /app to sys.path so `seed_data`
# is importable when the working directory is /app.
sys.path.insert(0, "/app")

from evercurrent.db.session import session_scope  # noqa: E402

# Reuse the SEED_CORPUS definitions verbatim.
from seed_data.slack_seed import SEED_CORPUS, SeedMessage  # type: ignore[import-not-found]  # noqa: E402

log = structlog.get_logger(__name__)

ORG_NAME: Final[str] = "Atlas Hardware"
ORG_AUTH0_ID: Final[str] = "org_atlas_demo"
PROJECT_NAME: Final[str] = "Atlas — chassis"

PERSONAS: Final[dict[str, tuple[str, list[str]]]] = {
    "Sarah Chen": ("mech_engineer", ["chassis"]),
    "Lin Park": ("qa_engineer", ["qa"]),
    "Mei Tanaka": ("supply_chain", ["supply_chain"]),
    "Dan Okafor": ("electrical_engineer", ["power"]),
    "Priya Iyer": ("firmware_engineer", ["firmware"]),
    "Tom Reilly": ("compliance", ["compliance"]),
    "Anna Volkov": ("manufacturing", ["manufacturing"]),
    "Raj Mehta": ("program_manager", []),
    "Karthik Rao": ("test_engineer", ["qa"]),
    "Elena Rossi": ("mech_engineer", ["chassis"]),
    "James Williams": ("electrical_engineer", ["power"]),
    "Nora Kim": ("program_manager", []),
}

CHANNEL_TOPIC: Final[dict[str, str]] = {
    "mech-design": "chassis",
    "electrical": "power",
    "firmware": "firmware",
    "qa-testing": "qa",
    "supply-chain": "supply_chain",
    "compliance": "compliance",
    "manufacturing": "manufacturing",
    "general": "program",
}

URGENCY_RULES: Final[list[tuple[str, str]]] = [
    ("decision", "high"),
    ("compress", "high"),
    ("blocked", "high"),
    ("brown out", "high"),
    ("risk", "high"),
    ("incident", "high"),
    ("fail", "high"),
    ("update", "normal"),
]


def _username(display_name: str) -> str:
    parts = display_name.lower().split()
    return parts[0]


def _urgency(text_body: str) -> str:
    lowered = text_body.lower()
    for needle, level in URGENCY_RULES:
        if needle in lowered:
            return level
    return "normal"


def _channel_name(slack_channel: str) -> str:
    return slack_channel.lstrip("#")


async def _upsert_demo_membership(session: object, org_id: uuid.UUID) -> uuid.UUID:
    row = (
        await session.execute(
            text(
                "SELECT id FROM org_memberships WHERE org_id = :oid "
                "AND auth0_user_id = 'demo|fallback'",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if row is not None:
        return uuid.UUID(str(row[0]))
    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO org_memberships (org_id, auth0_user_id, email, display_name,
                                              role, timezone)
                VALUES (:oid, 'demo|fallback', 'demo@evercurrent.local',
                        'Demo User', 'member', 'UTC')
                RETURNING id
                """,
            ),
            {"oid": str(org_id)},
        )
    ).first()
    return uuid.UUID(str(inserted[0]))


async def _upsert_org(session: object) -> uuid.UUID:
    row = (
        await session.execute(
            text("SELECT id FROM orgs WHERE name = :name"),
            {"name": ORG_NAME},
        )
    ).first()
    if row is not None:
        return uuid.UUID(str(row[0]))
    inserted = (
        await session.execute(
            text(
                "INSERT INTO orgs (auth0_org_id, name) VALUES (:aid, :name) RETURNING id",
            ),
            {"aid": ORG_AUTH0_ID, "name": ORG_NAME},
        )
    ).first()
    return uuid.UUID(str(inserted[0]))


async def _upsert_project(session: object, org_id: uuid.UUID) -> tuple[uuid.UUID, int]:
    row = (
        await session.execute(
            text("SELECT id, current_day FROM projects WHERE name = :n"),
            {"n": PROJECT_NAME},
        )
    ).first()
    if row is not None:
        return uuid.UUID(str(row[0])), int(row[1])
    start_date = dt.date.today() - dt.timedelta(days=42)
    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO projects (name, current_phase, current_day, start_date,
                                       phase_concerns, milestones, org_id)
                VALUES (:n, 'DVT', 42, :sd, '{}'::jsonb, '[]'::jsonb, :oid)
                RETURNING id
                """,
            ),
            {"n": PROJECT_NAME, "sd": start_date, "oid": str(org_id)},
        )
    ).first()
    return uuid.UUID(str(inserted[0])), 42


async def _upsert_user(
    session: object,
    *,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    display_name: str,
) -> uuid.UUID:
    username = _username(display_name)
    row = (
        await session.execute(
            text(
                "SELECT id FROM users WHERE project_id = :pid AND username = :u",
            ),
            {"pid": str(project_id), "u": username},
        )
    ).first()
    if row is not None:
        return uuid.UUID(str(row[0]))
    role, subsystems = PERSONAS.get(display_name, ("contributor", []))
    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO users (project_id, username, display_name, role,
                                    owned_subsystems, owned_parts, topic_weights, org_id)
                VALUES (:pid, :u, :dn, :r, :sub, ARRAY[]::text[], '{}'::jsonb, :oid)
                RETURNING id
                """,
            ),
            {
                "pid": str(project_id),
                "u": username,
                "dn": display_name,
                "r": role,
                "sub": subsystems,
                "oid": str(org_id),
            },
        )
    ).first()
    return uuid.UUID(str(inserted[0]))


async def _upsert_channel(
    session: object,
    *,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    name: str,
) -> uuid.UUID:
    row = (
        await session.execute(
            text("SELECT id FROM channels WHERE project_id = :pid AND name = :n"),
            {"pid": str(project_id), "n": name},
        )
    ).first()
    if row is not None:
        return uuid.UUID(str(row[0]))
    inserted = (
        await session.execute(
            text(
                "INSERT INTO channels (project_id, name, org_id) "
                "VALUES (:pid, :n, :oid) RETURNING id",
            ),
            {"pid": str(project_id), "n": name, "oid": str(org_id)},
        )
    ).first()
    return uuid.UUID(str(inserted[0]))


async def _insert_message(
    session: object,
    *,
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    channel_name: str,
    author_display_name: str,
    posted_at: dt.datetime,
    seed: SeedMessage,
    external_id: str,
) -> uuid.UUID | None:
    existing = (
        await session.execute(
            text(
                "SELECT id FROM messages WHERE source = 'seed' AND external_id = :eid",
            ),
            {"eid": external_id},
        )
    ).first()
    if existing is not None:
        return None
    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO messages (org_id, project_id, source, external_id,
                                       channel, author_display_name, text, posted_at)
                VALUES (:oid, :pid, 'seed', :eid, :ch, :adn, :t, :ts)
                RETURNING id
                """,
            ),
            {
                "oid": str(org_id),
                "pid": str(project_id),
                "eid": external_id,
                "ch": channel_name,
                "adn": author_display_name,
                "t": seed.text,
                "ts": posted_at,
            },
        )
    ).first()
    message_id = uuid.UUID(str(inserted[0]))

    topic = CHANNEL_TOPIC.get(channel_name, "general")
    urgency = _urgency(seed.text)
    affected = PERSONAS.get(seed.author, ("contributor", []))[1] or ["all"]
    await session.execute(
        text(
            """
            INSERT INTO message_tags (org_id, message_id, topic, urgency,
                                       entities, affected_roles, tagged_by_model)
            VALUES (:oid, :mid, :topic, :urg, ARRAY[]::text[], :affected, 'db_seed')
            """,
        ),
        {
            "oid": str(org_id),
            "mid": str(message_id),
            "topic": topic,
            "urg": urgency,
            "affected": affected,
        },
    )
    return message_id


async def seed() -> dict[str, int]:
    counts = {"users": 0, "channels": 0, "messages": 0, "skipped": 0}
    async with session_scope() as session:
        org_id = await _upsert_org(session)
        await _upsert_demo_membership(session, org_id)
        project_id, project_day = await _upsert_project(session, org_id)
        log.info("db_seed.project", project_id=str(project_id), day=project_day)

        users: dict[str, uuid.UUID] = {}
        for display_name in PERSONAS:
            uid = await _upsert_user(
                session,
                project_id=project_id,
                org_id=org_id,
                display_name=display_name,
            )
            users[display_name] = uid
            counts["users"] += 1

        channels: dict[str, uuid.UUID] = {}
        for slack_name in CHANNEL_TOPIC:
            cid = await _upsert_channel(
                session,
                project_id=project_id,
                org_id=org_id,
                name=slack_name,
            )
            channels[slack_name] = cid
            counts["channels"] += 1

        demo_membership_id = await _upsert_demo_membership(session, org_id)

        base = dt.datetime.now(dt.UTC) - dt.timedelta(days=14)
        for idx, seed_msg in enumerate(SEED_CORPUS):
            channel_name = _channel_name(seed_msg.channel)
            if channel_name not in channels:
                counts["skipped"] += 1
                continue
            if seed_msg.author not in users:
                counts["skipped"] += 1
                continue
            day_offset = min(14, idx // 6)
            posted_at = base + dt.timedelta(
                days=day_offset,
                hours=(idx * 47) % 24,
                minutes=(idx * 19) % 60,
            )
            external_id = f"seed-{idx:04d}"
            result = await _insert_message(
                session,
                project_id=project_id,
                org_id=org_id,
                channel_name=channel_name,
                author_display_name=seed_msg.author,
                posted_at=posted_at,
                seed=seed_msg,
                external_id=external_id,
            )
            if result is None:
                counts["skipped"] += 1
            else:
                counts["messages"] += 1
                # Score the message for the demo user so the digest pipeline
                # has signal to surface. Weight: recent + high-urgency wins.
                urgency_weight = 0.8 if _urgency(seed_msg.text) == "high" else 0.4
                recency_weight = (day_offset + 1) / 15.0
                score = round(urgency_weight + recency_weight, 3)
                await session.execute(
                    text(
                        """
                        INSERT INTO scores (org_id, project_member_id, message_id,
                                             score, reasons)
                        VALUES (:oid, :pmid, :mid, :score, CAST(:reasons AS jsonb))
                        ON CONFLICT (project_member_id, message_id) DO NOTHING
                        """,
                    ),
                    {
                        "oid": str(org_id),
                        "pmid": str(demo_membership_id),
                        "mid": str(result),
                        "score": score,
                        "reasons": json.dumps(
                            {"source": "db_seed", "urgency": _urgency(seed_msg.text)},
                        ),
                    },
                )

        await session.commit()
    return counts


def main() -> int:
    result = asyncio.run(seed())
    log.info("db_seed.complete", **result)
    print(f"Seed complete: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
