"""Relevance-scoring weights: the per-signal coefficients, constrained to be
non-negative and to sum to 1.0 so a score stays in [0, 1]."""

from __future__ import annotations

from dataclasses import dataclass

_SUM_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class Weights:
    role_match: float = 0.30
    subsystem_match: float = 0.25
    urgency_boost: float = 0.20
    phase_concern_match: float = 0.10
    topic_weight: float = 0.10
    cross_functional: float = 0.05

    def __post_init__(self) -> None:
        values = (
            self.role_match,
            self.subsystem_match,
            self.urgency_boost,
            self.phase_concern_match,
            self.topic_weight,
            self.cross_functional,
        )
        if any(v < 0.0 for v in values):
            raise ValueError("Weights must be non-negative")
        total = sum(values)
        if abs(total - 1.0) > _SUM_TOLERANCE:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    def as_dict(self) -> dict[str, float]:
        return {
            "role_match": self.role_match,
            "subsystem_match": self.subsystem_match,
            "urgency_boost": self.urgency_boost,
            "phase_concern_match": self.phase_concern_match,
            "topic_weight": self.topic_weight,
            "cross_functional": self.cross_functional,
        }


DEFAULT_WEIGHTS: Weights = Weights()
