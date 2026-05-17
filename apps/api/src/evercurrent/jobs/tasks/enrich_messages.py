"""Arq task: tag all messages for a given day."""

from __future__ import annotations

import os
import uuid
from typing import Any

import structlog

from evercurrent.db.repositories import MessageRepository
from evercurrent.db.session import session_scope
from evercurrent.enrichment.tagger import HeuristicTagger, LLMTagger, Tagger, chunked

log = structlog.get_logger(__name__)


def _tagger() -> Tagger:
    """Return an LLM tagger if a key is configured, else the heuristic one."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LLMTagger()
    return HeuristicTagger()


async def enrich_day(_ctx: dict[str, Any], project_id: str, day: int) -> dict[str, Any]:
    project_uuid = uuid.UUID(project_id)
    tagger = _tagger()
    tagged = 0
    skipped = 0

    async with session_scope() as session:
        msgs = MessageRepository(session)
        all_for_day = await msgs.list_for_day(project_uuid, day, with_tags=True)
        untagged = [em.message for em in all_for_day if em.tag is None]
        if not untagged:
            log.info("enrich.skip_all_tagged", day=day, total=len(all_for_day))
            return {"tagged": 0, "skipped": len(all_for_day), "day": day}

        for batch in chunked(untagged, size=15):
            tags = await tagger.tag_batch(batch)
            if len(tags) != len(batch):
                log.warning(
                    "enrich.batch_size_mismatch",
                    sent=len(batch),
                    received=len(tags),
                )
            for message, tag in zip(batch, tags, strict=False):
                await msgs.upsert_tag(
                    message_id=message.id,
                    topic=tag.topic,
                    urgency=tag.urgency,
                    affected_roles=tag.affected_roles,
                    entities=tag.entities,
                    raw_tag=tag.model_dump(mode="json"),
                )
                tagged += 1

        skipped = len(all_for_day) - tagged
        await session.commit()

    log.info("enrich.done", day=day, tagged=tagged, skipped=skipped)
    return {"tagged": tagged, "skipped": skipped, "day": day}
