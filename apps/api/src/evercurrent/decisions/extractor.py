"""LLM-driven decision extractor (Sonnet)."""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from pathlib import Path

import structlog

from evercurrent.db.repositories import DecisionRepository, MessageRepository
from evercurrent.db.session import session_scope
from evercurrent.decisions.schemas import ExtractedDecision
from evercurrent.domain.decisions import DecisionStatus
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

_DROP_BELOW_CONFIDENCE = 0.4
_PROPOSED_BELOW_CONFIDENCE = 0.6


def _llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def extract_decisions_for_day(  # noqa: C901
    project_id: uuid.UUID,
    day: int,
    *,
    provider: LLMProvider | None = None,
) -> int:
    """Extract + persist decisions for one day. Returns count written.

    Without an Anthropic key the function logs and returns 0 — the
    pipeline still works for everything else.
    """
    if not _llm_available():
        log.info("decisions.skip_no_key", day=day)
        return 0

    llm = provider or get_provider()
    prompt_tmpl = (PROMPTS_DIR / "extract.txt").read_text()

    async with session_scope() as session:
        msgs_repo = MessageRepository(session)
        decisions_repo = DecisionRepository(session)
        enriched = await msgs_repo.list_for_day(project_id, day, with_tags=True)
        if not enriched:
            return 0

        payload = [
            {
                "id": str(em.message.id),
                "ts": em.message.ts.isoformat(),
                "channel": em.channel_name,
                "author": em.author_username,
                "text": em.message.text,
            }
            for em in enriched
        ]
        prompt = prompt_tmpl.replace("{messages_json}", json.dumps(payload, indent=2))

        raw = await llm.complete_json(
            tier=ModelTier.DECISIONS,
            system=(
                "You extract structured engineering decisions from team "
                "conversations. Output JSON only."
            ),
            prompt=prompt,
            max_tokens=2048,
            temperature=0.1,
        )

        if not isinstance(raw, list):
            log.warning("decisions.unexpected_output", type=type(raw).__name__)
            return 0

        written = 0
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                extracted = ExtractedDecision.model_validate(entry)
            except (TypeError, ValueError) as exc:
                log.warning("decisions.invalid_entry", error=str(exc))
                continue
            if extracted.confidence < _DROP_BELOW_CONFIDENCE:
                continue
            status = extracted.status
            if extracted.confidence < _PROPOSED_BELOW_CONFIDENCE:
                status = DecisionStatus.PROPOSED

            decided_at = extracted.decided_at
            if decided_at.tzinfo is None:
                decided_at = decided_at.replace(tzinfo=dt.UTC)

            source_ids: list[uuid.UUID] = []
            for raw_id in extracted.source_message_ids:
                try:
                    source_ids.append(uuid.UUID(raw_id))
                except ValueError:
                    continue

            await decisions_repo.create(
                project_id=project_id,
                summary=extracted.summary,
                rationale=extracted.rationale,
                decided_by=extracted.decided_by,
                decided_at=decided_at,
                source_message_ids=source_ids,
                affected_subsystems=extracted.affected_subsystems,
                status=status,
                confidence=extracted.confidence,
            )
            written += 1

        await session.commit()

    log.info("decisions.extract.done", day=day, written=written)
    return written
