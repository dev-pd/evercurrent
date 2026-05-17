"""Message taggers — LLM-backed and heuristic fallback."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

import structlog

from evercurrent.domain.messages import Message, Urgency
from evercurrent.enrichment.schemas import MessageTagPayload
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mech_eng": (
        "chassis",
        "bracket",
        "extrusion",
        "arm",
        "gripper",
        "mech",
        "AL-",
        "mounting",
        "drop test",
        "thermal",
    ),
    "ee": ("PCB", "MOSFET", "motor driver", "power board", "voltage", "BMS", "EMC"),
    "supply_chain": (
        "supplier",
        "strike",
        "lead time",
        "sourcing",
        "BOM",
        "vendor",
        "AlumWest",
        "ExtruCo",
        "second source",
    ),
    "pm": ("schedule", "milestone", "risk register", "review", "ECO", "DVT exit", "PVT"),
    "qa": ("test", "drop", "thermal cycling", "chamber", "FAI", "first article", "failure"),
    "firmware": ("firmware", "PR #", "patch", "skip-band", "hysteresis", "retry"),
    "procurement": ("vendor", "PO", "quote", "AlumWest", "sourcing"),
}

TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("eco", ("ECO-", "ECO ", "engineering change")),
    ("supply_chain_disruption", ("strike", "force majeure", "supplier", "lead time")),
    ("firmware_bug", ("firmware", "PR #", "patch", "skip-band", "hysteresis", "retry")),
    ("test_result", ("test", "drop test", "thermal cycling", "chamber", "FAI", "first article")),
    ("thermal", ("thermal", "temperature", "°C", "heat", "cooling")),
    ("mechanical", ("bracket", "chassis", "mount", "arm", "gripper", "extrusion")),
    ("electrical", ("PCB", "MOSFET", "voltage", "current", "BMS", "EMC")),
    ("design_change", ("redesign", "tolerance", "material change", "spec change")),
    ("schedule_risk", ("schedule", "milestone", "slip", "risk register")),
    ("decision", ("approved", "sign-off", "release", "merge", "ship")),
    ("compliance", ("UL ", "FCC", "compliance", "regulatory")),
)

URGENCY_RULES: tuple[tuple[Urgency, tuple[str, ...]], ...] = (
    (Urgency.CRITICAL, ("force majeure", "line stop", "critical", "production halt")),
    (
        Urgency.HIGH,
        (
            "FAIL",
            "strike",
            "fast-track",
            "approved",
            "exit review",
            "blocker",
            "thermal failure",
            "regression",
        ),
    ),
    (Urgency.MEDIUM, ("worth a look", "follow-up", "investigate", "characterise", "anomaly")),
)

PART_NUMBER_PATTERN = re.compile(r"\b[A-Z]{2,5}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
ENTITY_KEYWORDS = (
    "bracket",
    "chassis",
    "gripper",
    "arm",
    "BMS",
    "motor driver",
    "power board",
    "supplier",
    "AlumWest",
    "ExtruCo",
    "MachineHaus",
    "BMS",
    "PVT",
    "DVT",
)


class Tagger(Protocol):
    async def tag_batch(self, messages: Sequence[Message]) -> list[MessageTagPayload]: ...


class HeuristicTagger:
    """Deterministic rule-based tagger.

    Not as nuanced as an LLM, but deterministic and free. Good enough for
    the demo, baseline eval comparisons, and CI smoke tests.
    """

    async def tag_batch(self, messages: Sequence[Message]) -> list[MessageTagPayload]:
        return [self._tag_one(m) for m in messages]

    def _tag_one(self, message: Message) -> MessageTagPayload:
        text = message.text
        lower = text.lower()
        topic = self._classify_topic(text, lower)
        urgency = self._classify_urgency(text, lower)
        affected = sorted(self._affected_roles(text, lower))
        entities = sorted(self._extract_entities(text))
        return MessageTagPayload(
            topic=topic,
            urgency=urgency,
            affected_roles=affected,
            entities=entities,
        )

    @staticmethod
    def _classify_topic(text: str, lower: str) -> str:
        for topic, kws in TOPIC_RULES:
            if any(kw.lower() in lower for kw in kws) or any(kw in text for kw in kws):
                return topic
        return "fyi"

    @staticmethod
    def _classify_urgency(text: str, lower: str) -> Urgency:
        for urgency, kws in URGENCY_RULES:
            if any(kw.lower() in lower for kw in kws) or any(kw in text for kw in kws):
                return urgency
        return Urgency.LOW

    @staticmethod
    def _affected_roles(text: str, lower: str) -> set[str]:
        roles: set[str] = set()
        for role, kws in ROLE_KEYWORDS.items():
            if any(kw.lower() in lower for kw in kws) or any(kw in text for kw in kws):
                roles.add(role)
        return roles

    @staticmethod
    def _extract_entities(text: str) -> set[str]:
        ents: set[str] = set(PART_NUMBER_PATTERN.findall(text))
        for kw in ENTITY_KEYWORDS:
            if kw.lower() in text.lower():
                ents.add(kw)
        return ents


class LLMTagger:
    """LLM-backed tagger. One Anthropic call per batch."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or get_provider()
        self._prompt = (PROMPTS_DIR / "tag_message.txt").read_text()
        self._system = (
            "You are a precise tagger for hardware engineering Slack messages. Output JSON only."
        )

    async def tag_batch(self, messages: Sequence[Message]) -> list[MessageTagPayload]:
        payload = [{"id": str(m.id), "channel": "", "text": m.text} for m in messages]
        prompt = self._prompt.replace("{messages_json}", json.dumps(payload, indent=2))
        prompt = prompt.replace("{len(messages)}", str(len(messages)))
        raw = await self._provider.complete_json(
            tier=ModelTier.TAGGING,
            system=self._system,
            prompt=prompt,
            max_tokens=4096,
            temperature=0.0,
        )
        if not isinstance(raw, list):
            log.warning("tagger.unexpected_output", type=type(raw).__name__)
            return []
        out: list[MessageTagPayload] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                out.append(MessageTagPayload.model_validate(entry))
            except (TypeError, ValueError) as exc:
                log.warning("tagger.invalid_entry", error=str(exc))
        return out


def chunked(seq: Sequence[Message], size: int) -> Iterable[list[Message]]:
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])
