"""Digest generation — Phase 8: per-member, per-day Sonnet briefings.

Public surface:

- `generate_digest(...)` — agent entry point.
- `enqueue_due_digests_now(...)` — beat helper.
- `repository` — persistence + read helpers.

Subphase order during the build: schemas first, prompts second, agent
third, scheduler fourth, then Beat + routes.
"""

from evercurrent.digest.agent import generate_digest
from evercurrent.digest.scheduler import (
    day_index_for_member,
    enqueue_due_digests_now,
    members_due_at,
)

__all__ = [
    "day_index_for_member",
    "enqueue_due_digests_now",
    "generate_digest",
    "members_due_at",
]
