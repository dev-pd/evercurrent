"""Scoring engine eval — scenario-based ranking checks."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import pytest

from evercurrent.domain.messages import EnrichedMessage, Message, MessageTag, Urgency
from evercurrent.domain.projects import Project
from evercurrent.domain.users import Role, User
from evercurrent.scoring.engine import score_messages_for_user
from tests.evals.conftest import emit_metric_table


def _make_user(spec: dict[str, Any]) -> User:
    return User(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        username="evaluser",
        display_name="Eval User",
        role=Role(spec["role"]),
        owned_subsystems=spec.get("owned_subsystems", []),
        owned_parts=spec.get("owned_parts", []),
        topic_weights=spec.get("topic_weights", {}),
        created_at=dt.datetime.now(dt.UTC),
    )


def _make_project(spec: dict[str, Any]) -> Project:
    return Project(
        id=uuid.uuid4(),
        name="eval-project",
        current_phase=spec["current_phase"],
        current_day=1,
        phase_concerns=spec.get("phase_concerns", {}),
        milestones=[],
        created_at=dt.datetime.now(dt.UTC),
        updated_at=dt.datetime.now(dt.UTC),
    )


def _make_enriched(spec: dict[str, Any]) -> EnrichedMessage:
    message_id = uuid.uuid4()
    project_id = uuid.uuid4()
    msg = Message(
        id=message_id,
        project_id=project_id,
        channel_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        thread_root_id=None,
        day=1,
        text=spec["text"],
        ts=dt.datetime.now(dt.UTC),
        reactions={},
        created_at=dt.datetime.now(dt.UTC),
    )
    tag_spec = spec.get("tag")
    tag = (
        MessageTag(
            message_id=message_id,
            topic=tag_spec["topic"],
            urgency=Urgency(tag_spec["urgency"]),
            affected_roles=tag_spec.get("affected_roles", []),
            entities=tag_spec.get("entities", []),
            raw_tag={},
            tagged_at=dt.datetime.now(dt.UTC),
        )
        if tag_spec
        else None
    )
    return EnrichedMessage(
        message=msg,
        tag=tag,
        author_username="bot",
        channel_name="#test",
    )


def test_scoring_scenarios(scoring_scenarios: list[dict[str, Any]]) -> None:
    rows: list[tuple[str, ...]] = [("scenario", "expected", "actual_top", "actual_score", "pass")]
    pass_count = 0
    for scenario in scoring_scenarios:
        project = _make_project(scenario["project"])
        user = _make_user(scenario["user"])
        enriched = [_make_enriched(m) for m in scenario["messages"]]
        # Inject a stable scenario_id-to-mock mapping so we can map ranking
        # results back to the JSON ids.
        id_map: dict[uuid.UUID, str] = {
            em.message.id: m["id"] for em, m in zip(enriched, scenario["messages"], strict=True)
        }
        scored = score_messages_for_user(enriched, user, project)
        actual_top_id = id_map[scored[0].enriched.message.id] if scored else "(none)"
        passed = actual_top_id == scenario["expected_top_id"]
        if passed:
            pass_count += 1
        rows.append(
            (
                scenario["name"],
                scenario["expected_top_id"],
                actual_top_id,
                f"{scored[0].score:.1f}" if scored else "-",
                "PASS" if passed else "FAIL",
            ),
        )
    total = len(scoring_scenarios)
    rows.append(("--- summary ---", "", "", f"pass {pass_count}/{total}", ""))
    emit_metric_table("scoring scenarios", rows)
    assert pass_count == total, f"scoring eval: {total - pass_count} scenarios failed"


@pytest.mark.parametrize("seed_size", [10, 100])
def test_scoring_is_deterministic(seed_size: int) -> None:
    """Same inputs in repeated runs produce identical rankings."""
    scenario = {
        "project": {
            "current_phase": "DVT",
            "phase_concerns": {"DVT": ["thermal margin"]},
        },
        "user": {
            "role": "mech_eng",
            "owned_subsystems": ["chassis"],
            "owned_parts": [],
        },
        "messages": [
            {
                "id": f"m{i}",
                "text": "Chassis thermal issue" if i % 3 == 0 else "FYI",
                "tag": {
                    "topic": "thermal" if i % 3 == 0 else "fyi",
                    "urgency": "high" if i % 3 == 0 else "low",
                    "affected_roles": ["mech_eng"] if i % 3 == 0 else [],
                    "entities": ["chassis"] if i % 3 == 0 else [],
                },
            }
            for i in range(seed_size)
        ],
    }
    project = _make_project(scenario["project"])
    user = _make_user(scenario["user"])
    enriched = [_make_enriched(m) for m in scenario["messages"]]
    first = [em.enriched.message.id for em in score_messages_for_user(enriched, user, project)]
    second = [em.enriched.message.id for em in score_messages_for_user(enriched, user, project)]
    assert first == second
