from __future__ import annotations

from typing import Any

import pytest

from evercurrent.scoring import WEIGHTS, ScoreInput, ScoreResult, score
from evercurrent.scoring.weights import Weights


def _default_input(**overrides: Any) -> ScoreInput:
    base: dict[str, Any] = {
        "member_role": "mech",
        "owned_subsystems": [],
        "topic_weights": {},
        "message_topic": None,
        "message_entities": [],
        "message_urgency": None,
        "message_affected_roles": [],
        "author_role": "firmware",
        "phase_concerns": [],
    }
    base.update(overrides)
    return ScoreInput(**base)


def test_score_zero_when_no_signals() -> None:
    inp = _default_input()

    result = score(inp)

    assert result.total == 0.0


def test_role_match_adds_role_weight() -> None:
    inp = _default_input(
        member_role="mech",
        message_affected_roles=["mech"],
    )

    result = score(inp)

    assert result.breakdown["role_match"] == 1.0


def test_subsystem_overlap_clamps_at_one() -> None:
    inp = _default_input(
        owned_subsystems=["chassis", "arm", "wheels", "sensors", "battery"],
        message_entities=["chassis", "arm", "wheels", "sensors", "battery"],
    )

    result = score(inp)

    assert result.breakdown["subsystem_match"] == 1.0


def test_urgency_critical_dominates() -> None:
    inp = _default_input(message_urgency="critical")

    result = score(inp)

    assert result.breakdown["urgency_boost"] == 1.0


def test_negative_topic_weight_suppresses_score() -> None:
    baseline = score(
        _default_input(
            member_role="mech",
            message_affected_roles=["mech"],
            message_topic="firmware",
        ),
    )
    suppressed = score(
        _default_input(
            member_role="mech",
            message_affected_roles=["mech"],
            message_topic="firmware",
            topic_weights={"firmware": -1.0},
        ),
    )

    assert suppressed.total < baseline.total


def test_score_clamps_between_zero_and_one() -> None:
    pumped = score(
        _default_input(
            member_role="mech",
            owned_subsystems=["chassis"],
            message_entities=["chassis"],
            message_urgency="critical",
            message_topic="thermal",
            phase_concerns=["thermal"],
            topic_weights={"thermal": 99.0},
            author_role="firmware",
            message_affected_roles=["mech"],
        ),
    )
    suppressed = score(
        _default_input(
            message_topic="firmware",
            topic_weights={"firmware": -99.0},
        ),
    )

    assert 0.0 <= pumped.total <= 1.0
    assert 0.0 <= suppressed.total <= 1.0


def test_cross_functional_only_when_subsystem_overlap() -> None:
    inp = _default_input(
        member_role="mech",
        author_role="firmware",
        owned_subsystems=["chassis"],
        message_entities=["unrelated"],
    )

    result = score(inp)

    assert result.breakdown["cross_functional"] == 0.0


def test_phase_concern_match_uses_current_phase() -> None:
    inp = _default_input(
        message_topic="thermal_margin",
        phase_concerns=["thermal_margin", "vibration"],
    )

    result = score(inp)

    assert result.breakdown["phase_concern_match"] == 0.7


def test_weights_sum_to_one_invariant() -> None:
    total = sum(WEIGHTS.values())

    assert total == pytest.approx(1.0)


def test_score_is_deterministic_for_same_inputs() -> None:
    inp = _default_input(
        member_role="mech",
        owned_subsystems=["chassis"],
        message_entities=["chassis"],
        message_urgency="high",
        message_topic="vibration",
        phase_concerns=["vibration"],
        topic_weights={"vibration": 0.3},
        author_role="firmware",
        message_affected_roles=["mech"],
    )

    first = score(inp)
    second = score(inp)

    assert first == second


def test_weights_dataclass_rejects_invalid_sum() -> None:
    with pytest.raises(ValueError, match=r"must sum to 1\.0"):
        Weights(
            role_match=0.5,
            subsystem_match=0.5,
            urgency_boost=0.5,
            phase_concern_match=0.0,
            topic_weight=0.0,
            cross_functional=0.0,
        )


def test_score_result_shape_includes_breakdown() -> None:
    inp = _default_input(
        member_role="mech",
        message_affected_roles=["mech"],
    )

    result = score(inp)

    assert isinstance(result, ScoreResult)
    assert set(result.breakdown) == {
        "role_match",
        "subsystem_match",
        "urgency_boost",
        "phase_concern_match",
        "topic_weight",
        "cross_functional",
    }
