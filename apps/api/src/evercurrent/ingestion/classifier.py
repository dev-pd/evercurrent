from __future__ import annotations

import json
from pathlib import Path

import structlog

from evercurrent.ingestion.chunking import Chunk
from evercurrent.ingestion.schemas import DocClassification
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "classify_doc.txt"
_SYSTEM = "You are a precise classifier for hardware engineering documents. Output JSON only."
_FIRST_N_CHUNKS = 3


def _render_prompt(title: str, chunks: list[Chunk]) -> str:
    template = _PROMPT_PATH.read_text()
    chunk_payload = [
        {"ordinal": c.ordinal, "section": c.section, "text": c.text}
        for c in chunks[:_FIRST_N_CHUNKS]
    ]
    return template.replace("{title}", title).replace(
        "{chunks}",
        json.dumps(chunk_payload, indent=2),
    )


async def classify_document(
    *,
    title: str,
    chunks: list[Chunk],
    provider: LLMProvider | None = None,
) -> DocClassification:
    if not chunks:
        return DocClassification(
            is_decision=False,
            kind="other",
            confidence=0.0,
            rationale="empty document",
        )
    llm = provider or get_provider()
    prompt = _render_prompt(title, chunks)
    raw = await llm.complete_json(
        tier=ModelTier.TAGGING,
        system=_SYSTEM,
        prompt=prompt,
        max_tokens=512,
        temperature=0.0,
    )
    if not isinstance(raw, dict):
        log.warning("classifier.unexpected_output", type=type(raw).__name__)
        return DocClassification(
            is_decision=False,
            kind="other",
            confidence=0.0,
            rationale="classifier returned non-object",
        )
    return DocClassification.model_validate(raw)
