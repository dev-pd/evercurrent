"""Pure focus computation.

A member's focus = owned subsystems (role) + role-adjacent concerns + current
phase concerns + learned behaviour (feedback-tuned topic weights). The result
is a ranked, normalized set of focus topics with provenance + trend, so the UI
can show *why* something is in focus and the digest judge can weight by it.
"""

from __future__ import annotations

from evercurrent.focus.schemas import FocusSource, FocusTopic, FocusTrend

# Concerns each engineering role tends to track beyond its owned subsystems.
ROLE_ADJACENT: dict[str, list[str]] = {
    "mech": ["chassis", "thermal", "tolerance"],
    "ee": ["power", "thermal", "firmware"],
    "fw": ["firmware", "integration"],
    "sw": ["firmware", "integration"],
    "qa": ["qa", "reliability", "test"],
    "supply": ["supply_chain", "cost", "lead_time"],
    "em": ["schedule", "cost", "risk"],
    "pm": ["scope", "customer", "schedule"],
}

_LABELS: dict[str, str] = {
    "supply_chain": "Supply chain",
    "lead_time": "Lead time",
}

_W_OWNED = 0.7
_W_ADJACENT = 0.4
_W_PHASE = 0.5
_W_LEARNED = 0.6  # max contribution from a +1.0 topic weight


def _label(topic: str) -> str:
    return _LABELS.get(topic, topic.replace("_", " ").capitalize())


def compute_focus(
    *,
    eng_role: str | None,
    owned_subsystems: list[str],
    phase_concerns: list[str],
    topic_weights: dict[str, float],
    limit: int = 6,
) -> list[FocusTopic]:
    weights: dict[str, float] = {}
    sources: dict[str, set[FocusSource]] = {}
    trends: dict[str, FocusTrend] = {}

    def add(topic: str, weight: float, source: FocusSource) -> None:
        key = topic.strip().lower()
        if not key:
            return
        weights[key] = weights.get(key, 0.0) + weight
        sources.setdefault(key, set()).add(source)
        trends.setdefault(key, "flat")

    for s in owned_subsystems:
        add(s, _W_OWNED, "role")
    for s in ROLE_ADJACENT.get(eng_role or "", []):
        add(s, _W_ADJACENT, "role")
    for c in phase_concerns:
        add(c, _W_PHASE, "phase")
    for topic, tw in topic_weights.items():
        if tw == 0:
            continue
        add(topic, _W_LEARNED * max(-1.0, min(1.0, tw)), "learned")
        trends[topic.strip().lower()] = "up" if tw > 0 else "down"

    if not weights:
        return []

    top = max(weights.values()) or 1.0
    items = [
        FocusTopic(
            topic=key,
            label=_label(key),
            weight=round(max(0.0, val) / top, 3),
            sources=sorted(sources[key]),
            trend=trends[key],
        )
        for key, val in weights.items()
        if val > 0
    ]
    items.sort(key=lambda f: f.weight, reverse=True)
    return items[:limit]
