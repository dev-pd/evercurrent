"""Eve — the proactive cross-team insight agent.

Unlike the workflow stages (router tag, scoring, digest), Eve is a genuine
tool-using agent: given the goal "find a high-impact, cross-subsystem change,"
it decides which tools to call (search messages, search spec docs, query
decisions), gathers context in a loop, and emits one structured insight.
"""

from evercurrent.eve.agent import run_eve

__all__ = ["run_eve"]
