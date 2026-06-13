from __future__ import annotations

from evercurrent.scoring.schemas import ScoreInput, ScoreResult
from evercurrent.scoring.weights import DEFAULT_WEIGHTS, Weights

_URGENCY_MAP: dict[str, float] = {
    "critical": 1.0,
    "high": 0.6,
    "normal": 0.3,
    "low": 0.0,
}

_PHASE_CONCERN_HIT: float = 0.7
_CROSS_FUNCTIONAL_HIT: float = 0.4


def _role_match(inp: ScoreInput) -> float:
    return 1.0 if inp.member_role in inp.message_affected_roles else 0.0


def _subsystem_match(inp: ScoreInput) -> float:
    owned = set(inp.owned_subsystems)
    overlap = sum(1 for e in inp.message_entities if e in owned)
    return min(1.0, float(overlap))


def _urgency_boost(inp: ScoreInput) -> float:
    if inp.message_urgency is None:
        return 0.0
    return _URGENCY_MAP.get(inp.message_urgency, 0.0)


def _phase_concern_match(inp: ScoreInput) -> float:
    if inp.message_topic is None:
        return 0.0
    return _PHASE_CONCERN_HIT if inp.message_topic in inp.phase_concerns else 0.0


def _topic_weight(inp: ScoreInput) -> float:
    if inp.message_topic is None:
        return 0.0
    raw = inp.topic_weights.get(inp.message_topic, 0.0)
    return max(-1.0, min(1.0, raw))


def _cross_functional(inp: ScoreInput) -> float:
    if inp.author_role == inp.member_role:
        return 0.0
    owned = set(inp.owned_subsystems)
    has_overlap = any(e in owned for e in inp.message_entities)
    return _CROSS_FUNCTIONAL_HIT if has_overlap else 0.0


def score(inp: ScoreInput, weights: Weights | None = None) -> ScoreResult:
    w = weights or DEFAULT_WEIGHTS
    breakdown: dict[str, float] = {
        "role_match": _role_match(inp),
        "subsystem_match": _subsystem_match(inp),
        "urgency_boost": _urgency_boost(inp),
        "phase_concern_match": _phase_concern_match(inp),
        "topic_weight": _topic_weight(inp),
        "cross_functional": _cross_functional(inp),
    }
    raw = (
        w.role_match * breakdown["role_match"]
        + w.subsystem_match * breakdown["subsystem_match"]
        + w.urgency_boost * breakdown["urgency_boost"]
        + w.phase_concern_match * breakdown["phase_concern_match"]
        + w.topic_weight * breakdown["topic_weight"]
        + w.cross_functional * breakdown["cross_functional"]
    )
    total = max(0.0, min(1.0, raw))
    return ScoreResult(total=total, breakdown=breakdown)
