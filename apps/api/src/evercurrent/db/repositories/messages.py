"""SQL for messages: single-message lookups used by the card and scoring
pipelines (returns plain row dicts the callers shape further)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Raw SQL matches the migrated `messages` schema. The ORM `Message` model is
# stale (channel_id/author_id/ts vs the real channel/author_*/posted_at) and is
# never queried, so repositories talk to the table directly.
_MESSAGE_COLUMNS = (
    "id, org_id, project_id, source, external_id, channel, thread_root_id, "
    "author_membership_id, author_display_name, text, posted_at, ingested_at"
)


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, message_id: uuid.UUID) -> dict[str, Any] | None:
        row = (
            (
                await self._s.execute(
                    text(f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE id = :id"),
                    {"id": str(message_id)},
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None
