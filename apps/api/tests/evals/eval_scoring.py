"""Scoring eval — 20 scenarios, pure-Python, no LLM.

Each scenario gives one "focus" message with expected relative rank
out of 20. We score the focus message against a population of 20
deterministic distractor messages and check whether the focus sits at
its expected rank. Aggregate metric: Spearman rank correlation between
expected and actual ranks.
"""

from __future__ import annotations

from typing import Any

from evercurrent.scoring.engine import score
from evercurrent.scoring.schemas import ScoreInput
from tests.evals.conftest import emit_metric_table, write_report
from tests.evals.runner import spearman_rho, warn_if_below_baseline

_DISTRACTOR_TEMPLATES: list[dict[str, Any]] = [
    {"topic": "fyi", "entities": [], "urgency": "low", "affected_roles": []},
    {"topic": "social", "entities": [], "urgency": "low", "affected_roles": []},
    {"topic": "status_update", "entities": [], "urgency": "low", "affected_roles": ["pm"]},
    {"topic": "general", "entities": [], "urgency": "low", "affected_roles": []},
    {"topic": "logistics", "entities": [], "urgency": "low", "affected_roles": []},
    {"topic": "calendar", "entities": [], "urgency": "low", "affected_roles": []},
    {
        "topic": "status_update",
        "entities": ["lunch"],
        "urgency": "low",
        "affected_roles": [],
    },
    {
        "topic": "test_result",
        "entities": ["drop test"],
        "urgency": "low",
        "affected_roles": ["qa"],
    },
    {
        "topic": "supplier_qual",
        "entities": ["unrelated_supplier"],
        "urgency": "normal",
        "affected_roles": ["supply"],
    },
    {
        "topic": "question",
        "entities": [],
        "urgency": "low",
        "affected_roles": ["em"],
    },
    {
        "topic": "milestone",
        "entities": ["phase gate"],
        "urgency": "normal",
        "affected_roles": ["pm"],
    },
    {
        "topic": "firmware",
        "entities": ["motor controller"],
        "urgency": "normal",
        "affected_roles": ["fw"],
    },
    {
        "topic": "supply_chain",
        "entities": ["unrelated_supplier"],
        "urgency": "normal",
        "affected_roles": ["supply"],
    },
    {
        "topic": "test_plan",
        "entities": ["EMC"],
        "urgency": "normal",
        "affected_roles": ["ee"],
    },
    {
        "topic": "risk",
        "entities": ["unrelated_part"],
        "urgency": "normal",
        "affected_roles": ["em"],
    },
    {
        "topic": "eco",
        "entities": ["unrelated_eco"],
        "urgency": "normal",
        "affected_roles": ["em"],
    },
    {
        "topic": "status_update",
        "entities": ["FEA"],
        "urgency": "normal",
        "affected_roles": ["mech"],
    },
    {
        "topic": "test_result",
        "entities": ["bench"],
        "urgency": "normal",
        "affected_roles": ["qa"],
    },
    {
        "topic": "supplier_qual",
        "entities": ["other_supplier"],
        "urgency": "low",
        "affected_roles": ["supply"],
    },
    {
        "topic": "logistics",
        "entities": [],
        "urgency": "low",
        "affected_roles": [],
    },
]


def _score_focus_rank(scenario: dict[str, Any]) -> int:
    """Score the focus message against 20 distractors, return its 0-based rank."""
    member = scenario["member"]
    focus = scenario["message"]
    member_role = member["member_role"]
    owned = member["owned_subsystems"]
    weights = member["topic_weights"]
    author_role = member["author_role"]
    phase_concerns = member["phase_concerns"]

    def _score_msg(msg: dict[str, Any]) -> float:
        return score(
            ScoreInput(
                member_role=member_role,
                owned_subsystems=owned,
                topic_weights=weights,
                message_topic=msg["topic"],
                message_entities=msg["entities"],
                message_urgency=msg["urgency"],
                message_affected_roles=msg["affected_roles"],
                author_role=author_role,
                phase_concerns=phase_concerns,
            ),
        ).total

    focus_score = _score_msg(focus)
    distractor_scores = [_score_msg(d) for d in _DISTRACTOR_TEMPLATES]
    all_scores = [focus_score, *distractor_scores]
    sorted_desc = sorted(all_scores, reverse=True)
    return sorted_desc.index(focus_score)


def test_scoring_rank_correlation(scoring_scenarios: list[dict[str, Any]]) -> None:
    """Per scenario, score focus + distractors; assert ranking matches expectation."""
    expected_ranks: list[int] = []
    actual_ranks: list[int] = []
    rows: list[tuple[str, ...]] = [
        ("id", "name", "expected_rank", "actual_rank", "delta"),
    ]
    for scenario in scoring_scenarios:
        actual = _score_focus_rank(scenario)
        expected = int(scenario["expected_rank"])
        expected_ranks.append(expected)
        actual_ranks.append(actual)
        rows.append(
            (
                scenario["id"],
                scenario["name"],
                str(expected),
                str(actual),
                str(actual - expected),
            ),
        )

    rho = spearman_rho(expected_ranks, actual_ranks)
    deltas = [abs(a - e) for a, e in zip(actual_ranks, expected_ranks, strict=True)]
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0

    rows.append(("--- summary ---", "spearman", f"{rho:.3f}", "0.80", ""))
    rows.append(("--- summary ---", "mean |delta|", f"{mean_delta:.2f}", "", ""))
    emit_metric_table("scoring eval (20 scenarios)", rows)
    warn_if_below_baseline("scoring_rank_correlation", rho)

    write_report(
        "scoring",
        {
            "n_scenarios": len(scoring_scenarios),
            "metrics": {
                "spearman_rho": rho,
                "mean_abs_rank_delta": mean_delta,
            },
            "per_scenario": [
                {
                    "id": s["id"],
                    "expected_rank": e,
                    "actual_rank": a,
                }
                for s, e, a in zip(
                    scoring_scenarios,
                    expected_ranks,
                    actual_ranks,
                    strict=True,
                )
            ],
        },
    )
