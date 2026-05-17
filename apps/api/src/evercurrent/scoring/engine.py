"""Scoring engine.

`score_messages_for_user` takes a list of EnrichedMessages, a user, and a
project, and emits ScoredMessage objects ranked highest-first. The engine
is pure: it does not touch the DB. Repositories load EnrichedMessages and
hand them in; the service layer calls this and persists results.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from evercurrent.domain.messages import EnrichedMessage, Urgency
from evercurrent.domain.projects import Project
from evercurrent.domain.users import User
from evercurrent.scoring.dependencies import dependency_match
from evercurrent.scoring.weights import Weights, default_weights

_THREAD_ACTIVITY_THRESHOLD = 5
_DEFAULT_TOP_N = 20


@dataclass(frozen=True, slots=True)
class ScoredMessage:
    enriched: EnrichedMessage
    score: float
    breakdown: dict[str, float]

    @property
    def message_id(self) -> str:
        return str(self.enriched.message.id)


def _phase_concerns_for(project: Project) -> set[str]:
    concerns = project.phase_concerns.get(project.current_phase, [])
    return {c.lower() for c in concerns}


def score_message_for_user(
    enriched: EnrichedMessage,
    user: User,
    project: Project,
    *,
    thread_reply_count: int = 0,
    weights: Weights | None = None,
) -> ScoredMessage:
    """Score one enriched message for one user. Pure function."""
    w = weights or default_weights()
    breakdown: dict[str, float] = {}
    score = 0.0

    tag = enriched.tag
    urgency = tag.urgency if tag else Urgency.LOW

    # 1. Role-direct hit.
    if tag and user.role.value in tag.affected_roles:
        score += w.role_direct
        breakdown["role_direct"] = w.role_direct

    # 2. Cross-functional dependency hit (owned subsystem/part appears in entities).
    if tag and dependency_match(tag.entities, user.owned_subsystems, user.owned_parts):
        score += w.cross_functional
        breakdown["cross_functional"] = w.cross_functional

    # 3. Urgency.
    urgency_value = w.urgency.get(urgency, 0.0)
    if urgency_value:
        score += urgency_value
        breakdown["urgency"] = urgency_value

    # 4. Thread activity (active threads matter more).
    if thread_reply_count >= _THREAD_ACTIVITY_THRESHOLD:
        score += w.thread_activity
        breakdown["thread_activity"] = w.thread_activity

    # 5. Phase concern match — topic intersects this phase's concerns.
    if tag:
        concerns = _phase_concerns_for(project)
        topic_lower = tag.topic.lower().replace("_", " ")
        if any(c in topic_lower or topic_lower in c for c in concerns):
            score += w.phase_match
            breakdown["phase_match"] = w.phase_match

    # 6. Per-user learned topic weight (from thumbs feedback).
    if tag:
        learned = float(user.topic_weights.get(tag.topic, 0.0))
        if learned:
            score += w.feedback_unit * learned
            breakdown["feedback"] = w.feedback_unit * learned

    return ScoredMessage(enriched=enriched, score=score, breakdown=breakdown)


def score_messages_for_user(
    enriched_messages: Sequence[EnrichedMessage],
    user: User,
    project: Project,
    *,
    thread_reply_counts: dict[str, int] | None = None,
    weights: Weights | None = None,
    top_n: int | None = _DEFAULT_TOP_N,
) -> list[ScoredMessage]:
    """Score and rank all messages for one user. Returns top_n highest-first."""
    counts = thread_reply_counts or {}
    scored: list[ScoredMessage] = []
    for em in enriched_messages:
        replies = 0
        if em.message.thread_root_id is not None:
            replies = counts.get(str(em.message.thread_root_id), 0)
        else:
            replies = counts.get(str(em.message.id), 0)
        scored.append(
            score_message_for_user(
                em,
                user,
                project,
                thread_reply_count=replies,
                weights=weights,
            ),
        )
    scored.sort(key=lambda s: (-s.score, s.enriched.message.ts))
    return scored if top_n is None else scored[:top_n]
