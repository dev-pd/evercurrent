"""Claude-backed generator for realistic Slack chatter, by persona + phase.

Used to seed a rich historical corpus (posted to Slack, then time-shifted in
the DB) and by the live demo-chatter task. Bulk runs on Haiku; the live task
passes the DIGEST tier for higher quality on low volume.
"""

from __future__ import annotations

import re
from importlib import resources
from typing import Any

import structlog

from evercurrent.ingestion.personas import Persona, personas_for_channel
from evercurrent.ingestion.synthetic_schemas import (
    GeneratedBatch,
    GeneratedMessage,
    Phase,
)
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

_PROMPT_PKG = "evercurrent.ingestion.prompts"
_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

CHANNEL_TOPICS: dict[str, str] = {
    "electrical": "power, rails, regulators, battery + BMS, EMI",
    "mech-design": "chassis, enclosure, thermal, ECOs, tolerances, drawings",
    "firmware": "firmware releases, OTA, drivers, power management, BMS tuning",
    "qa-testing": "reliability, HTOL, drop test, thermal regression, RMAs",
    "supply-chain": "lead-times, POs, cell + alloy sourcing, allocation, MOQ",
    "manufacturing": "build readiness, tooling, yield, line setup, DFM",
    "compliance": "certifications, safety, phase gates, sign-offs",
    "general": "cross-team status, decisions, program-level updates",
}


def _load(name: str) -> str:
    return resources.files(_PROMPT_PKG).joinpath(name).read_text(encoding="utf-8")


def _render(template: str, ctx: dict[str, str]) -> str:
    return _VAR.sub(lambda m: ctx.get(m.group(1), ""), template)


def _roster(personas: list[Persona]) -> str:
    return "\n".join(f"- {p.name} ({p.eng_role}): {p.voice}" for p in personas)


async def generate_batch(
    *,
    channel: str,
    phase: Phase,
    count: int,
    threads: int = 2,
    tier: ModelTier = ModelTier.TAGGING,
    llm: LLMProvider | None = None,
) -> list[GeneratedMessage]:
    provider = llm or get_provider()
    personas = personas_for_channel(channel)
    ctx = {
        "channel": channel,
        "channel_topic": CHANNEL_TOPICS.get(channel, "engineering discussion"),
        "phase_label": phase.label,
        "phase_summary": phase.summary,
        "concerns": ", ".join(phase.concerns),
        "roster": _roster(personas),
        "count": str(count),
        "threads": str(threads),
    }
    system = _load("synthetic_system.txt")
    prompt = _render(_load("synthetic_user.txt.j2"), ctx)
    raw: dict[str, Any] | list[Any] = await provider.complete_json(
        tier=tier,
        system=system,
        prompt=prompt,
        max_tokens=4096,
        temperature=1.0,
    )
    payload = raw if isinstance(raw, dict) else {"messages": raw}
    batch = GeneratedBatch.model_validate(payload)
    valid_names = {p.name for p in personas}
    out = [m for m in batch.messages if m.author in valid_names and m.text.strip()]
    log.info(
        "synthetic.batch",
        channel=channel,
        phase=phase.key,
        requested=count,
        returned=len(out),
    )
    return out
