from __future__ import annotations

import asyncio
from typing import Any

import pytest

from evercurrent.llm.client import LLMProvider
from evercurrent.routing.router_agent import classify
from tests.evals.conftest import emit_metric_table, write_report
from tests.evals.runner import jaccard, warn_if_below_baseline


def _topic_match(predicted: str | None, expected: str | None) -> bool:
    if expected is None:
        return predicted is None
    if predicted is None:
        return False
    p = predicted.strip().lower()
    e = expected.strip().lower()
    if not p or not e:
        return False
    return e in p or p in e


async def _classify_one(
    llm: LLMProvider,
    row: dict[str, Any],
) -> tuple[str | None, str, list[str], list[str], bool]:
    decision = await classify(
        llm=llm,
        message_text=row["message_text"],
        channel=row["channel"],
        author_display_name="eval_user",
        author_role=row.get("author_role", "em"),
        thread_parent_text=None,
        project_phase="DVT",
    )
    return (
        decision.topic,
        decision.urgency,
        decision.entities,
        decision.affected_roles,
        decision.should_create_card,
    )


def test_router_accuracy(
    router_labels: list[dict[str, Any]],
    llm_provider: LLMProvider,
) -> None:
    state: dict[str, Any] = {
        "topic_hits": 0,
        "urgency_hits": 0,
        "scc_hits": 0,
        "entity_jaccards": [],
        "role_jaccards": [],
    }
    detail_rows: list[tuple[str, ...]] = [
        ("id", "topic", "urgency", "entities", "roles", "card?"),
    ]
    failures: list[dict[str, Any]] = []

    async def _run() -> None:
        for row in router_labels:
            try:
                topic, urgency, entities, roles, scc = await _classify_one(
                    llm_provider,
                    row,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": row["id"], "error": str(exc)})
                detail_rows.append(
                    (row["id"], "ERR", "ERR", "ERR", "ERR", "ERR"),
                )
                continue

            expected = row["expected"]
            t_ok = _topic_match(topic, expected["topic"])
            u_ok = urgency == expected["urgency"]
            scc_ok = scc == expected["should_create_card"]
            e_jac = jaccard(entities, expected["entities"])
            r_jac = jaccard(roles, expected["affected_roles"])

            if t_ok:
                state["topic_hits"] += 1
            if u_ok:
                state["urgency_hits"] += 1
            if scc_ok:
                state["scc_hits"] += 1
            state["entity_jaccards"].append(e_jac)
            state["role_jaccards"].append(r_jac)

            detail_rows.append(
                (
                    row["id"],
                    "OK" if t_ok else f"FAIL({topic})",
                    "OK" if u_ok else f"FAIL({urgency})",
                    f"{e_jac:.2f}",
                    f"{r_jac:.2f}",
                    "OK" if scc_ok else "FAIL",
                ),
            )

    asyncio.run(_run())

    total = len(router_labels) - len(failures)
    if total <= 0:
        pytest.fail(f"router eval: every row failed ({len(failures)} errors)")

    topic_acc = state["topic_hits"] / total
    urgency_acc = state["urgency_hits"] / total
    scc_acc = state["scc_hits"] / total
    e_jacs = state["entity_jaccards"]
    r_jacs = state["role_jaccards"]
    entity_avg = sum(e_jacs) / len(e_jacs) if e_jacs else 0.0
    role_avg = sum(r_jacs) / len(r_jacs) if r_jacs else 0.0

    summary_rows: list[tuple[str, ...]] = [
        ("field", "metric", "score", "baseline"),
        ("topic", "accuracy", f"{topic_acc:.3f}", "0.85"),
        ("urgency", "accuracy", f"{urgency_acc:.3f}", "0.90"),
        ("entities", "jaccard", f"{entity_avg:.3f}", "0.60"),
        ("affected_roles", "jaccard", f"{role_avg:.3f}", "0.70"),
        ("should_create_card", "accuracy", f"{scc_acc:.3f}", "0.85"),
        ("--- errors ---", "", str(len(failures)), ""),
    ]
    emit_metric_table("router eval (50 labelled messages)", summary_rows)
    emit_metric_table("router eval per-row", detail_rows)

    warn_if_below_baseline("router_topic", topic_acc)
    warn_if_below_baseline("router_urgency", urgency_acc)
    warn_if_below_baseline("router_entities", entity_avg)
    warn_if_below_baseline("router_affected_roles", role_avg)
    warn_if_below_baseline("router_should_create_card", scc_acc)

    write_report(
        "router",
        {
            "n_rows": len(router_labels),
            "errors": failures,
            "metrics": {
                "topic_accuracy": topic_acc,
                "urgency_accuracy": urgency_acc,
                "entities_jaccard": entity_avg,
                "affected_roles_jaccard": role_avg,
                "should_create_card_accuracy": scc_acc,
            },
        },
    )
