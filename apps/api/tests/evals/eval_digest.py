"""Digest eval — 5 scenarios, Sonnet writer, Sonnet-as-judge.

We bypass the digest agent's DB hooks and call Sonnet directly with the
production prompts rendered over the hand-built `DigestContext`. The
generated digest is then scored by a second Sonnet call against the
rubric in `judge_prompts/digest_rubric.txt`.

This shape avoids bootstrapping the full multi-tenancy schema (org +
project + membership + scores) inside the eval, which is plumbing for
a downstream concern (persistence) not the thing we're measuring (the
writer's quality).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from importlib import resources
from typing import Any

import pytest
from jinja2 import Environment, StrictUndefined

from evercurrent.digest.schemas import (
    CardSummary,
    DigestContext,
    DigestDraft,
    MemberProfile,
    ProjectSnapshot,
    ScoredItem,
)
from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier
from tests.evals.conftest import emit_metric_table, write_report
from tests.evals.runner import warn_if_below_baseline

_PROMPT_PKG = "evercurrent.digest.prompts"
_MAX_TOKENS = 2048

_jinja_env = Environment(
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701  prompt text, not HTML
)


def _load_system_prompt() -> str:
    return resources.files(_PROMPT_PKG).joinpath("system.txt").read_text(encoding="utf-8")


def _load_user_template() -> str:
    return resources.files(_PROMPT_PKG).joinpath("user.txt.j2").read_text(encoding="utf-8")


def _build_context(scenario: dict[str, Any]) -> DigestContext:
    m = scenario["member"]
    member = MemberProfile(
        project_member_id=uuid.uuid4(),
        display_name=m["display_name"],
        role=m["role"],
        timezone=m["timezone"],
        owned_subsystems=m["owned_subsystems"],
        topic_weights={k: float(v) for k, v in m.get("topic_weights", {}).items()},
    )
    p = scenario["project"]
    project = ProjectSnapshot(
        project_id=uuid.uuid4(),
        name=p["name"],
        current_phase=p["current_phase"],
        phase_concerns=p["phase_concerns"],
    )
    scored = [
        ScoredItem(
            message_id=uuid.UUID(item["message_id"]),
            score=float(item["score"]),
            topic=item.get("topic"),
            urgency=item.get("urgency"),
            channel=item.get("channel"),
            author=item.get("author"),
            text=item["text"],
            posted_at=dt.datetime.fromisoformat(item["posted_at"]),
        )
        for item in scenario["top_scored_items"]
    ]
    cards = [
        CardSummary(
            card_id=uuid.UUID(c["card_id"]),
            kind=c["kind"],
            summary=c["summary"],
            status=c["status"],
            affected_subsystems=c.get("affected_subsystems", []),
            updated_at=dt.datetime.now(dt.UTC),
        )
        for c in scenario.get("open_cards", [])
    ]
    return DigestContext(
        member=member,
        project=project,
        day_index=int(scenario["day_index"]),
        top_scored_items=scored,
        open_cards=cards,
        prior_digests=[],
    )


def _render_user_prompt(ctx: DigestContext) -> str:
    tmpl = _jinja_env.from_string(_load_user_template())
    return tmpl.render(
        member=ctx.member,
        project=ctx.project,
        day_index=ctx.day_index,
        top_scored_items=ctx.top_scored_items,
        open_cards=ctx.open_cards,
        prior_digests=ctx.prior_digests,
    )


async def _generate(llm: LLMProvider, ctx: DigestContext) -> DigestDraft:
    system = _load_system_prompt()
    user_prompt = _render_user_prompt(ctx)
    payload = await llm.complete_json(
        tier=ModelTier.DIGEST,
        system=system,
        prompt=user_prompt,
        max_tokens=_MAX_TOKENS,
        temperature=0.3,
    )
    return DigestDraft.model_validate(payload)


_JUDGE_USER_TEMPLATE = """Member profile:
- name: {name}
- role: {role}
- owned subsystems: {subsystems}

Input source items the digest writer had access to:
{source_block}

Expected critical topics this digest should touch on:
{expected_topics}

Digest under review:

{digest_md}

Cited card_ids: {cited_cards}
Cited message_ids: {cited_messages}

Score the digest now, returning the JSON object the rubric describes.
"""


def _format_sources(ctx: DigestContext) -> str:
    msg_lines = [
        f"- [msg:{item.message_id}] urgency={item.urgency} topic={item.topic}: "
        f"{item.text!r}"
        for item in ctx.top_scored_items
    ]
    card_lines = [
        f"- [card:{card.card_id}] {card.kind}: {card.summary!r}"
        for card in ctx.open_cards
    ]
    lines = [*msg_lines, *card_lines]
    return "\n".join(lines) if lines else "(empty)"


async def _judge(
    llm: LLMProvider,
    judge_prompt: str,
    scenario: dict[str, Any],
    ctx: DigestContext,
    draft: DigestDraft,
) -> dict[str, Any]:
    user = _JUDGE_USER_TEMPLATE.format(
        name=ctx.member.display_name,
        role=ctx.member.role,
        subsystems=", ".join(ctx.member.owned_subsystems) or "(none)",
        source_block=_format_sources(ctx),
        expected_topics=", ".join(scenario["expected_critical_topics"]),
        digest_md=draft.content_md,
        cited_cards=", ".join(str(c) for c in draft.card_ids) or "(none)",
        cited_messages=", ".join(str(m) for m in draft.message_ids) or "(none)",
    )
    payload = await llm.complete_json(
        tier=ModelTier.DIGEST,
        system=judge_prompt,
        prompt=user,
        max_tokens=512,
        temperature=0.0,
    )
    if isinstance(payload, list):
        msg = "judge returned a list instead of an object"
        raise TypeError(msg)
    return payload


def test_digest_rubric_judge(
    digest_scenarios: list[dict[str, Any]],
    digest_judge_prompt: str,
    llm_provider: LLMProvider,
) -> None:
    """For each scenario: generate, judge, accumulate per-axis means."""
    rows: list[tuple[str, ...]] = [
        ("id", "relevance", "citations", "voice", "length", "notes"),
    ]
    per_scenario: list[dict[str, Any]] = []
    axes = ("relevance", "citation_correctness", "voice_second_person", "length_budget")
    sums = dict.fromkeys(axes, 0.0)
    counted = 0
    failures: list[dict[str, Any]] = []

    async def _run() -> None:
        nonlocal counted
        for scenario in digest_scenarios:
            ctx = _build_context(scenario)
            try:
                draft = await _generate(llm_provider, ctx)
                scores = await _judge(
                    llm_provider,
                    digest_judge_prompt,
                    scenario,
                    ctx,
                    draft,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": scenario["id"], "error": str(exc)})
                rows.append((scenario["id"], "ERR", "ERR", "ERR", "ERR", str(exc)[:40]))
                continue

            counted += 1
            for axis in axes:
                sums[axis] += float(scores.get(axis, 0))
            rows.append(
                (
                    scenario["id"],
                    str(scores.get("relevance", "?")),
                    str(scores.get("citation_correctness", "?")),
                    str(scores.get("voice_second_person", "?")),
                    str(scores.get("length_budget", "?")),
                    str(scores.get("notes", ""))[:40],
                ),
            )
            per_scenario.append(
                {
                    "id": scenario["id"],
                    "scores": scores,
                    "digest_md": draft.content_md,
                },
            )

    asyncio.run(_run())

    if counted == 0:
        pytest.fail(f"digest eval: every scenario failed ({len(failures)} errors)")

    means = {axis: sums[axis] / counted for axis in axes}
    rows.append(
        (
            "--- mean ---",
            f"{means['relevance']:.2f}",
            f"{means['citation_correctness']:.2f}",
            f"{means['voice_second_person']:.2f}",
            f"{means['length_budget']:.2f}",
            f"n={counted}",
        ),
    )
    emit_metric_table("digest eval (5 scenarios, Sonnet judge)", rows)

    warn_if_below_baseline("digest_relevance", means["relevance"])
    warn_if_below_baseline("digest_citation_correctness", means["citation_correctness"])
    warn_if_below_baseline("digest_voice_second_person", means["voice_second_person"])
    warn_if_below_baseline("digest_length_budget", means["length_budget"])

    write_report(
        "digest",
        {
            "n_scenarios": len(digest_scenarios),
            "errors": failures,
            "metrics": {"means": means},
            "per_scenario": per_scenario,
        },
    )


__all__ = ["test_digest_rubric_judge"]
