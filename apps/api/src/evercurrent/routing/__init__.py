"""Router agent: per-message Haiku classifier + Card trigger.

The router reads a normalised Slack message, decides whether it is a
decision candidate / risk / question / noise, tags it with topic +
urgency + entities + affected roles, and signals downstream whether
the message should become a Knowledge Card.

Public surface is intentionally small: a `RouterDecision` schema and a
`classify` coroutine. The Celery wrapper lives in
`evercurrent.jobs.tasks.route_message`.
"""

from __future__ import annotations

from evercurrent.routing.router_agent import classify
from evercurrent.routing.schemas import RouterDecision

__all__ = ["RouterDecision", "classify"]
