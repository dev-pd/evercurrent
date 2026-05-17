"""Digest generation.

Two implementations:
- `LLMDigestGenerator`: Sonnet-driven, follows the prompt template.
- `HeuristicDigestGenerator`: deterministic markdown template that works
  without API keys. Used in CI, evals, and demos when the key is unset.

`generate_all_digests_for_day` orchestrates: score messages per user,
hand the top-N to the generator, persist the digest. Idempotent
(digests has UNIQUE (user_id, day)).
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import structlog

from evercurrent.db.repositories import (
    DigestRepository,
    MessageRepository,
    ProjectRepository,
    UserRepository,
)
from evercurrent.db.session import session_scope
from evercurrent.domain.messages import EnrichedMessage
from evercurrent.domain.projects import Project
from evercurrent.domain.users import User
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier
from evercurrent.scoring.engine import ScoredMessage, score_messages_for_user

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
TOP_N = 8
_TOP_PRIORITY_SCORE = 12.0
_WATCH_OUT_SCORE = 6.0
_HIGH_URGENCY_BUMP = 5.0
_EXCERPT_MAX_CHARS = 180
_EXCERPT_ELLIPSIS_CUT = 177


class DigestGenerator(Protocol):
    async def generate(
        self,
        *,
        user: User,
        project: Project,
        top_messages: Sequence[ScoredMessage],
    ) -> str: ...


def _milestone_summary(project: Project) -> tuple[str, str]:
    if not project.milestones:
        return ("none", "n/a")
    upcoming = project.milestones[0]
    return (upcoming.get("name", "upcoming milestone"), upcoming.get("target_date", "n/a"))


def _scored_to_payload(scored: Sequence[ScoredMessage]) -> list[dict[str, object]]:
    return [
        {
            "msg_id": s.message_id,
            "score": round(s.score, 2),
            "channel": s.enriched.channel_name,
            "author": s.enriched.author_username,
            "text": s.enriched.message.text,
            "topic": s.enriched.tag.topic if s.enriched.tag else "fyi",
            "urgency": s.enriched.tag.urgency.value if s.enriched.tag else "low",
            "breakdown": s.breakdown,
        }
        for s in scored
    ]


class HeuristicDigestGenerator:
    """Template-only digest. No LLM. Deterministic markdown."""

    async def generate(
        self,
        *,
        user: User,
        project: Project,
        top_messages: Sequence[ScoredMessage],
    ) -> str:
        if not top_messages:
            return f"No items for you on day {project.current_day}.\n"

        top_priority: list[ScoredMessage] = []
        watch_outs: list[ScoredMessage] = []
        fyi: list[ScoredMessage] = []
        for s in top_messages:
            urgency = s.enriched.tag.urgency.value if s.enriched.tag else "low"
            if urgency == "critical" or s.score >= _TOP_PRIORITY_SCORE:
                top_priority.append(s)
            elif urgency in {"high", "medium"} or s.score >= _WATCH_OUT_SCORE:
                watch_outs.append(s)
            else:
                fyi.append(s)

        lines: list[str] = [
            f"Day {project.current_day} briefing for **{user.display_name}** "
            f"({user.role.value}) — project in {project.current_phase}.",
            "",
        ]

        def render_bucket(name: str, items: Sequence[ScoredMessage]) -> None:
            if not items:
                return
            lines.append(f"## {name}")
            for s in items:
                msg = s.enriched
                why = self._why_this_matters(s, user)
                excerpt = msg.message.text.strip().split("\n", 1)[0]
                if len(excerpt) > _EXCERPT_MAX_CHARS:
                    excerpt = excerpt[:_EXCERPT_ELLIPSIS_CUT] + "..."
                lines.append(
                    f"- [msg_{msg.message.id}] **{msg.channel_name}** "
                    f"({msg.author_username}): {excerpt}",
                )
                lines.append(f"  - _Why this matters to you:_ {why}")
            lines.append("")

        render_bucket("Top priority", top_priority)
        render_bucket("Watch-outs", watch_outs)
        render_bucket("FYI", fyi)
        return "\n".join(lines)

    @staticmethod
    def _why_this_matters(s: ScoredMessage, user: User) -> str:
        breakdown = s.breakdown
        reasons: list[str] = []
        if "role_direct" in breakdown:
            reasons.append(f"directly hits your {user.role.value} role")
        if "cross_functional" in breakdown:
            reasons.append("touches a subsystem or part you own")
        if "phase_match" in breakdown:
            reasons.append("aligns with current phase concerns")
        if "urgency" in breakdown and breakdown["urgency"] >= _HIGH_URGENCY_BUMP:
            reasons.append("flagged high urgency")
        if not reasons:
            reasons.append("flagged for your awareness")
        return "; ".join(reasons)


class LLMDigestGenerator:
    """LLM-backed generator using Sonnet."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or get_provider()
        self._prompt = (PROMPTS_DIR / "generate.txt").read_text()
        self._system = "You write concise, actionable engineering briefings."

    async def generate(
        self,
        *,
        user: User,
        project: Project,
        top_messages: Sequence[ScoredMessage],
    ) -> str:
        milestone_name, milestone_date = _milestone_summary(project)
        payload = _scored_to_payload(top_messages)
        prompt = self._prompt
        prompt = prompt.replace("{user_name}", user.display_name)
        prompt = prompt.replace("{user_role}", user.role.value)
        prompt = prompt.replace("{owned_subsystems}", ", ".join(user.owned_subsystems) or "n/a")
        prompt = prompt.replace("{project_name}", project.name)
        prompt = prompt.replace("{project_phase}", project.current_phase)
        prompt = prompt.replace("{next_milestone_name}", milestone_name)
        prompt = prompt.replace("{days_until_milestone}", milestone_date)
        prompt = prompt.replace("{top_messages_json}", json.dumps(payload, indent=2))
        result = await self._provider.complete(
            tier=ModelTier.DIGEST,
            system=self._system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        return result.text.strip()


def _pick_generator() -> DigestGenerator:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LLMDigestGenerator()
    return HeuristicDigestGenerator()


async def generate_digest_for_user(
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    day: int,
    phase: str | None = None,
    enriched_messages: Sequence[EnrichedMessage] | None = None,
) -> str | None:
    """Score + generate + persist a digest for one (user, day, phase) cell.

    `phase` overrides the project's current_phase — used by the
    pre-compute step that sweeps every phase variant.
    """
    async with session_scope() as session:
        projects = ProjectRepository(session)
        users = UserRepository(session)
        msgs = MessageRepository(session)
        digests = DigestRepository(session)

        project = await projects.get_by_id(project_id)
        user = await users.get_by_id(user_id)
        if project is None or user is None:
            return None

        # Score against the requested phase, not necessarily the live
        # project phase. We swap the field on a copy so we don't persist
        # the override.
        effective_phase = phase or project.current_phase
        scoring_project = project.model_copy(update={"current_phase": effective_phase})

        if enriched_messages is None:
            enriched_messages = await msgs.list_for_day(project_id, day, with_tags=True)

        scored = score_messages_for_user(
            enriched_messages,
            user,
            scoring_project,
            top_n=TOP_N,
        )
        generator = _pick_generator()
        content = await generator.generate(
            user=user,
            project=scoring_project,
            top_messages=scored,
        )

        await digests.upsert(
            user_id=user.id,
            project_id=project.id,
            day=day,
            phase=effective_phase,
            content_md=content,
            item_message_ids=[s.enriched.message.id for s in scored],
        )
        await session.commit()
        return content


async def generate_all_digests_for_day(
    project_id: uuid.UUID,
    day: int,
    *,
    phase: str | None = None,
) -> int:
    """Generate digests for every user in the project on the given day."""
    async with session_scope() as session:
        users_repo = UserRepository(session)
        msgs_repo = MessageRepository(session)
        users = await users_repo.list_for_project(project_id)
        enriched = await msgs_repo.list_for_day(project_id, day, with_tags=True)

    count = 0
    for user in users:
        content = await generate_digest_for_user(
            project_id=project_id,
            user_id=user.id,
            day=day,
            phase=phase,
            enriched_messages=enriched,
        )
        if content is not None:
            count += 1
            log.info("digest.generate.user_done", user_id=str(user.id), day=day)

    return count


_PROJECT_PHASES = ("concept", "design", "EVT", "DVT", "PVT", "MP")


async def precompute_all_digests(
    project_id: uuid.UUID,
    *,
    days: Sequence[int] = (1, 2, 3, 4, 5),
    phases: Sequence[str] = _PROJECT_PHASES,
) -> int:
    """Pre-compute every (user, day, phase) digest variant.

    Heavy — 8 users * 5 days * 6 phases = 240 Sonnet calls. Run once at
    seed time so the UI never waits on an LLM during a phase swap.
    """
    total = 0
    for phase in phases:
        for day in days:
            written = await generate_all_digests_for_day(
                project_id,
                day,
                phase=phase,
            )
            log.info("digest.precompute.cell_done", phase=phase, day=day, written=written)
            total += written
    return total


def main() -> None:
    """CLI: `python -m evercurrent.digest.generator [--day N|--all]`."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Generate / precompute digests.")
    parser.add_argument("--day", type=int, help="Generate for one day (current phase only)")
    parser.add_argument("--all", action="store_true", help="Precompute every (user, day, phase)")
    parser.add_argument("--project-name", default="Warehouse Robot v2")
    args = parser.parse_args()

    async def _run() -> None:
        async with session_scope() as session:
            project = await ProjectRepository(session).get_by_name(args.project_name)
        if project is None:
            msg = f"project {args.project_name!r} not found; run `make seed` first."
            raise RuntimeError(msg)
        if args.all:
            written = await precompute_all_digests(project.id)
            log.info("digest.cli.precompute_done", total=written)
        elif args.day:
            written = await generate_all_digests_for_day(project.id, args.day)
            log.info("digest.cli.day_done", day=args.day, total=written)
        else:
            log.info("digest.cli.usage", message="Pass --day N or --all.")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
