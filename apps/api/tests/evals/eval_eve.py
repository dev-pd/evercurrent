from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import get_settings
from evercurrent.insights import run_eve
from evercurrent.jobs.tasks.eve_insight import _gate
from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier
from evercurrent.mcp.client import InProcessMCPClient
from tests.evals.conftest import emit_metric_table, write_report
from tests.evals.runner import warn_if_below_baseline

_MAX_TOKENS = 512


class _FakeMCP(InProcessMCPClient):
    """Serves a scenario's fixed corpus so Eve can be evaluated offline,
    with no database. Each search tool returns its slice of the corpus."""

    def __init__(self, corpus: dict[str, list[dict[str, Any]]]) -> None:
        self._corpus = corpus

    async def call(
        self,
        tool_name: str,
        session: AsyncSession,  # noqa: ARG002  signature parity with the real client
        args: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        return self._corpus.get(tool_name, [])


_JUDGE_USER_TEMPLATE = """Scenario had a planted conflict: {planted}

Evidence corpus Eve could retrieve:
{corpus_block}

Insight Eve emitted:
- title: {title}
- summary: {summary}
- affected_subsystems: {subsystems}
- conflicts: {conflicts}
- cited sources: {sources}

Score the insight now, returning the JSON object the rubric describes.
"""


def _corpus_block(corpus: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        f"- [{tool}] {it.get('author', '?')}: {it.get('snippet', '')!r}"
        for tool, items in corpus.items()
        for it in items
    ]
    return "\n".join(lines) if lines else "(empty)"


async def _judge(
    llm: LLMProvider,
    judge_prompt: str,
    scenario: dict[str, Any],
    insight: dict[str, Any],
) -> dict[str, Any]:
    user = _JUDGE_USER_TEMPLATE.format(
        planted=scenario["planted"],
        corpus_block=_corpus_block(scenario["corpus"]),
        title=insight.get("title", ""),
        summary=insight.get("summary", ""),
        subsystems=", ".join(insight.get("affected_subsystems", [])) or "(none)",
        conflicts=json.dumps(insight.get("conflicts", []))[:800],
        sources=json.dumps(insight.get("sources", []))[:800],
    )
    payload = await llm.complete_json(
        tier=ModelTier.DIGEST,
        system=judge_prompt,
        prompt=user,
        max_tokens=_MAX_TOKENS,
        temperature=0.0,
    )
    if isinstance(payload, list):
        msg = "judge returned a list instead of an object"
        raise TypeError(msg)
    return payload


async def _run_scenario(
    llm: LLMProvider,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    run = await run_eve(
        cast("AsyncSession", None),
        project_id=uuid.uuid4(),
        llm=llm,
        mcp=_FakeMCP(scenario["corpus"]),
    )
    emitted = run.insight
    accepted = False
    if emitted is not None:
        reason, grounded = _gate(emitted, run, settings)
        emitted["sources"] = grounded
        accepted = reason is None
    return {"emitted": emitted, "accepted": accepted, "searched": run.searched}


def test_eve_eval(
    eve_scenarios: list[dict[str, Any]],
    eve_judge_prompt: str,
    llm_provider: LLMProvider,
) -> None:
    rows: list[tuple[str, ...]] = [
        ("id", "planted", "emitted", "accepted", "faith", "rel", "spec"),
    ]
    per_scenario: list[dict[str, Any]] = []
    planted_total = planted_surfaced = clean_total = clean_abstained = 0
    faith_sum = rel_sum = spec_sum = 0.0
    judged = 0

    async def _run() -> None:
        nonlocal planted_total, planted_surfaced, clean_total, clean_abstained
        nonlocal faith_sum, rel_sum, spec_sum, judged
        for scenario in eve_scenarios:
            outcome = await _run_scenario(llm_provider, scenario)
            emitted, accepted = outcome["emitted"], outcome["accepted"]

            if scenario["should_emit"]:
                planted_total += 1
                planted_surfaced += int(accepted)
            else:
                clean_total += 1
                clean_abstained += int(not accepted)

            scores: dict[str, Any] = {}
            if emitted is not None and scenario["planted"]:
                scores = await _judge(llm_provider, eve_judge_prompt, scenario, emitted)
                judged += 1
                faith_sum += float(scores.get("faithfulness", 0))
                rel_sum += float(scores.get("relevance", 0))
                spec_sum += float(scores.get("specificity", 0))

            rows.append(
                (
                    scenario["id"],
                    str(scenario["planted"]),
                    str(emitted is not None),
                    str(accepted),
                    str(scores.get("faithfulness", "-")),
                    str(scores.get("relevance", "-")),
                    str(scores.get("specificity", "-")),
                ),
            )
            per_scenario.append(
                {
                    "id": scenario["id"],
                    "planted": scenario["planted"],
                    "emitted": emitted is not None,
                    "accepted": accepted,
                    "searched": outcome["searched"],
                    "scores": scores,
                },
            )

    asyncio.run(_run())

    recall = planted_surfaced / planted_total if planted_total else 0.0
    precision = clean_abstained / clean_total if clean_total else 0.0
    faith = faith_sum / judged if judged else 0.0
    rel = rel_sum / judged if judged else 0.0
    spec = spec_sum / judged if judged else 0.0

    rows.append(
        (
            "--- summary ---",
            f"recall={recall:.2f}",
            f"prec={precision:.2f}",
            f"n={len(eve_scenarios)}",
            f"{faith:.2f}",
            f"{rel:.2f}",
            f"{spec:.2f}",
        ),
    )
    emit_metric_table("eve eval (grounding gate + Sonnet judge)", rows)

    warn_if_below_baseline("eve_recall", recall)
    warn_if_below_baseline("eve_precision", precision)
    warn_if_below_baseline("eve_faithfulness", faith)
    warn_if_below_baseline("eve_relevance", rel)

    write_report(
        "eve",
        {
            "n_scenarios": len(eve_scenarios),
            "metrics": {
                "recall": recall,
                "precision": precision,
                "faithfulness": faith,
                "relevance": rel,
                "specificity": spec,
            },
            "per_scenario": per_scenario,
        },
    )

    if planted_total == 0:
        pytest.fail("eve eval: no planted scenarios to measure recall")


__all__ = ["test_eve_eval"]
