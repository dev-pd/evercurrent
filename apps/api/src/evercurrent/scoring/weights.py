"""Scoring weights. Tune here, never inline in the engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from evercurrent.domain.messages import Urgency


@dataclass(frozen=True, slots=True)
class Weights:
    role_direct: float = 10.0  # user.role in tag.affected_roles
    cross_functional: float = 7.0  # owned subsystem / part in tag.entities
    thread_activity: float = 2.0  # >=5 replies in thread
    feedback_unit: float = 1.0  # multiplier on per-topic learned weight
    urgency: dict[Urgency, float] = field(
        default_factory=lambda: {
            Urgency.LOW: 0.0,
            Urgency.MEDIUM: 2.0,
            Urgency.HIGH: 5.0,
            # Critical sits above role_direct + cross_functional so an
            # enterprise-wide line-stop surfaces even when the user has no
            # direct stake.
            Urgency.CRITICAL: 20.0,
        },
    )
    phase_match: float = 4.0  # tag.topic appears in project.phase_concerns


def default_weights() -> Weights:
    return Weights()
