"""get_thread_context tool.

Given a message id, returns the thread's root message and all replies
in posted-at order. If the supplied message is itself a reply, the tool
walks up to the root (`thread_root_id`). If the message has no thread
(no root + no replies), returns a `ThreadContext` with that message as
root and an empty replies list. Missing/unknown ids return `None`.
"""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.mcp.schemas import MessageRef, ThreadContext

log = structlog.get_logger(__name__)

# Post Phase-8 messages are denormalized (channel text + author_display_name
# + posted_at) — no channels/users joins.
_LOOKUP_SQL = text(
    """
    SELECT
        m.id AS id,
        m.thread_root_id AS thread_root_id,
        m.channel AS channel,
        m.author_display_name AS author,
        m.text AS text,
        m.posted_at AS posted_at
    FROM messages m
    WHERE m.id = :message_id
    """,
).bindparams(bindparam("message_id"))

_REPLIES_SQL = text(
    """
    SELECT
        m.id AS id,
        m.channel AS channel,
        m.author_display_name AS author,
        m.text AS text,
        m.posted_at AS posted_at
    FROM messages m
    WHERE m.thread_root_id = :root_id
      AND m.id <> :root_id
    ORDER BY m.posted_at ASC
    """,
).bindparams(bindparam("root_id"))


async def get_thread_context(
    session: AsyncSession,
    *,
    message_id: uuid.UUID,
) -> ThreadContext | None:
    """Return the thread (root + replies) containing `message_id`, or None."""
    start = time.perf_counter()

    initial = (
        await session.execute(_LOOKUP_SQL, {"message_id": message_id})
    ).mappings().first()
    if initial is None:
        log.info(
            "mcp.tool_call",
            tool_name="get_thread_context",
            message_id=str(message_id),
            result_count=0,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return None

    root_id: uuid.UUID = initial["thread_root_id"] or initial["id"]
    if root_id == initial["id"]:
        root_row = initial
    else:
        root_row = (
            await session.execute(_LOOKUP_SQL, {"message_id": root_id})
        ).mappings().first()
        if root_row is None:
            root_row = initial
            root_id = initial["id"]

    root = MessageRef(
        id=root_row["id"],
        channel=root_row["channel"],
        author=root_row["author"],
        text=root_row["text"],
        posted_at=root_row["posted_at"],
        score=None,
    )

    reply_result = await session.execute(
        _REPLIES_SQL,
        {"root_id": root_id},
    )
    replies = [
        MessageRef(
            id=r["id"],
            channel=r["channel"],
            author=r["author"],
            text=r["text"],
            posted_at=r["posted_at"],
            score=None,
        )
        for r in reply_result.mappings()
    ]

    duration_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "mcp.tool_call",
        tool_name="get_thread_context",
        message_id=str(message_id),
        root_id=str(root_id),
        result_count=1 + len(replies),
        duration_ms=duration_ms,
    )
    return ThreadContext(root=root, replies=replies)
