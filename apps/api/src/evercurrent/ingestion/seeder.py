"""Seeder CLI: loads committed seed JSON/markdown into the database.

Usage (inside the api container):
    python -m evercurrent.ingestion.seeder            # base seed
    python -m evercurrent.ingestion.seeder --load-messages
    python -m evercurrent.ingestion.seeder --load-docs
    python -m evercurrent.ingestion.seeder --all

Idempotent: rerunning upserts projects/users/channels and replaces
messages + documents for the project.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import delete

from evercurrent.db.models import (
    Document as DocumentModel,
)
from evercurrent.db.models import (
    Message as MessageModel,
)
from evercurrent.db.repositories import (
    ChannelRepository,
    DocumentRepository,
    MessageRepository,
    ProjectRepository,
    UserRepository,
)
from evercurrent.db.session import session_scope
from evercurrent.domain.documents import DocumentKind
from evercurrent.domain.users import Role

log = structlog.get_logger(__name__)

SEED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "seed_data"


async def seed_base() -> uuid.UUID:
    """Load project + users + channels. Returns the project id."""
    project_path = SEED_DIR / "project.json"
    users_path = SEED_DIR / "users.json"
    channels_path = SEED_DIR / "channels.json"

    project_data = json.loads(project_path.read_text())
    users_data = json.loads(users_path.read_text())
    channels_data = json.loads(channels_path.read_text())

    async with session_scope() as session:
        projects = ProjectRepository(session)
        users = UserRepository(session)
        channels = ChannelRepository(session)

        project = await projects.upsert(
            name=project_data["name"],
            current_phase=project_data["current_phase"],
            current_day=project_data.get("current_day", 1),
            phase_concerns=project_data.get("phase_concerns", {}),
            milestones=project_data.get("milestones", []),
        )
        log.info("seed.project.upsert", project_id=str(project.id), name=project.name)

        for u in users_data:
            await users.upsert(
                project_id=project.id,
                username=u["username"],
                display_name=u["display_name"],
                role=Role(u["role"]),
                owned_subsystems=u.get("owned_subsystems", []),
                owned_parts=u.get("owned_parts", []),
            )
        log.info("seed.users.upsert", count=len(users_data))

        for c in channels_data:
            await channels.upsert(
                project_id=project.id,
                name=c["name"],
                description=c.get("description"),
            )
        log.info("seed.channels.upsert", count=len(channels_data))

        await session.commit()
        return project.id


async def load_messages(project_id: uuid.UUID) -> int:
    """Load committed seed_data/messages_day_*.json. Replaces existing.

    The generator (see `ingestion.generator`) writes one JSON file per day.
    Each entry has channel, author_username, text, ts, optional thread_root_id,
    optional reactions, and (where the generator emitted them) a stable
    \"client_id\" the seeder uses to wire up thread roots inside a day.
    """
    files = sorted(SEED_DIR.glob("messages_day_*.json"))
    if not files:
        log.info("seed.messages.skip", reason="no message files yet")
        return 0

    total = 0
    async with session_scope() as session:
        users = UserRepository(session)
        channels = ChannelRepository(session)
        msgs = MessageRepository(session)

        # Idempotent: blow away prior messages for the project, then reload.
        await session.execute(delete(MessageModel).where(MessageModel.project_id == project_id))

        # Cache username/channel -> id lookups.
        user_by_username = {u.username: u for u in await users.list_for_project(project_id)}
        channel_by_name = {c.name: c for c in await channels.list_for_project(project_id)}

        for path in files:
            payload: list[dict[str, Any]] = json.loads(path.read_text())
            client_id_to_uuid: dict[str, uuid.UUID] = {}
            day = int(path.stem.removeprefix("messages_day_"))
            for entry in payload:
                channel = channel_by_name.get(entry["channel"])
                author = user_by_username.get(entry["author_username"])
                if channel is None or author is None:
                    log.warning(
                        "seed.messages.skip_unknown",
                        channel=entry.get("channel"),
                        author=entry.get("author_username"),
                    )
                    continue
                thread_root_id = None
                root_ref = entry.get("thread_root_id")
                if root_ref:
                    thread_root_id = client_id_to_uuid.get(root_ref)
                ts = dt.datetime.fromisoformat(entry["ts"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.UTC)
                created = await msgs.create(
                    project_id=project_id,
                    channel_id=channel.id,
                    author_id=author.id,
                    day=day,
                    text=entry["text"],
                    ts=ts,
                    thread_root_id=thread_root_id,
                    reactions=entry.get("reactions", {}),
                )
                if "client_id" in entry:
                    client_id_to_uuid[entry["client_id"]] = created.id
                total += 1
            log.info("seed.messages.loaded", day=day, count=len(payload))
        await session.commit()
    return total


async def load_docs(project_id: uuid.UUID) -> int:
    """Load committed seed_data/docs/*.md as Documents."""
    docs_dir = SEED_DIR / "docs"
    if not docs_dir.exists():
        log.info("seed.docs.skip", reason="no docs dir")
        return 0

    kind_by_stem = {
        "prd": DocumentKind.PRD,
        "bom": DocumentKind.BOM,
        "eco_log": DocumentKind.ECO_LOG,
        "test_report_thermal": DocumentKind.TEST_REPORT_THERMAL,
        "test_report_drop": DocumentKind.TEST_REPORT_DROP,
    }

    total = 0
    async with session_scope() as session:
        documents = DocumentRepository(session)
        await session.execute(delete(DocumentModel).where(DocumentModel.project_id == project_id))
        for path in sorted(docs_dir.glob("*.md")):
            stem = path.stem.lower()
            kind = kind_by_stem.get(stem, DocumentKind.OTHER)
            title = stem.replace("_", " ").upper() if kind != DocumentKind.OTHER else stem
            body = path.read_text()
            await documents.upsert(
                project_id=project_id,
                kind=kind,
                title=title,
                body=body,
            )
            total += 1
        await session.commit()
    log.info("seed.docs.loaded", count=total)
    return total


async def run(args: argparse.Namespace) -> None:
    project_id = await seed_base()
    if args.load_messages or args.all:
        loaded = await load_messages(project_id)
        log.info("seed.messages.done", count=loaded)
    if args.load_docs or args.all:
        loaded = await load_docs(project_id)
        log.info("seed.docs.done", count=loaded)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the EverCurrent DB.")
    parser.add_argument("--load-messages", action="store_true", help="Load messages_day_*.json")
    parser.add_argument("--load-docs", action="store_true", help="Load docs/*.md")
    parser.add_argument("--all", action="store_true", help="Base + messages + docs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
