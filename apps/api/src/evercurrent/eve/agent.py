"""The Eve agent loop.

Sonnet is given a goal + a toolbox (the read-only MCP tools + an `emit_insight`
action). It reasons, calls tools to gather context, and finishes by calling
`emit_insight` with a structured ProactiveInsight. We dispatch tool calls
through the in-process MCP client (injecting project_id) and feed results back
until the agent emits — or we hit the iteration cap.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.llm.client import LLMProvider, ToolSpec, get_provider
from evercurrent.llm.tiering import ModelTier
from evercurrent.mcp.client import InProcessMCPClient

log = structlog.get_logger(__name__)

_MAX_TURNS = 8

EVE_SYSTEM = """You are Eve, a proactive engineering insight agent for a hardware team.
Your job: find ONE high-impact change that ripples across subsystems, or a conflict
between team chatter and the formal spec documents, and report it.

Use the tools to gather evidence first:
- search_messages: what the team is discussing (decisions, escalations).
- search_documents: the formal specs/BOM/requirements (the source of truth).
- query_cards: extracted decisions and risks.

Look especially for a CHANGE (a spec value moved, a supplier swapped, a requirement
escalated) and trace its blast radius: which subsystems, what cost/schedule/risk,
who should be looped in. A chatter-vs-spec mismatch (e.g. Slack says 22 Nm but the
PRD says 15 Nm) is the strongest signal.

If spec documents are unavailable (search_documents returns nothing), still
produce your best insight grounded in the Slack messages and decision cards —
e.g. a cross-subsystem change or risk surfaced in chatter.

Do at most 3-4 tool calls, then call emit_insight EXACTLY ONCE with a complete,
well-grounded insight. You MUST populate `sources` with the actual Slack
snippets and cards you used as evidence (kind, channel/author, a short verbatim
snippet) — at least two. Cite real snippets you found. Do not invent numbers."""

# Read tools the agent may call (project_id is injected server-side, not by the LLM).
_READ_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="search_messages",
        description="Semantic search over Slack messages. Returns relevant message snippets.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "what to look for"}},
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="search_documents",
        description="Semantic search over spec/BOM/requirement PDFs. The formal source of truth.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="query_cards",
        description="List extracted decisions/risks. Optional kind=decision|risk, status=open.",
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "status": {"type": "string"},
            },
        },
    ),
]

_EMIT_TOOL = ToolSpec(
    name="emit_insight",
    description="Emit the final structured insight. Call this once when you have evidence.",
    input_schema={
        "type": "object",
        "properties": {
            "req_id": {"type": "string", "description": "e.g. REQ-245 or a short id"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "affected_subsystems": {"type": "array", "items": {"type": "string"}},
            "before": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                },
            },
            "after": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                },
            },
            "conflicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subsystem": {"type": "string"},
                        "severity": {"type": "string", "enum": ["info", "warn", "critical"]},
                        "title": {"type": "string"},
                        "detail": {"type": "string"},
                        "impact": {"type": "string"},
                    },
                },
            },
            "sources": {
                "type": "array",
                "minItems": 2,
                "description": "Real evidence you used: at least two Slack snippets or cards.",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["slack", "doc"]},
                        "channel": {"type": "string"},
                        "author": {"type": "string"},
                        "snippet": {"type": "string"},
                    },
                    "required": ["kind", "snippet"],
                },
            },
            "impact_summary": {
                "type": "object",
                "properties": {
                    "cost": {"type": "string"},
                    "schedule": {"type": "string"},
                    "revenue_at_risk": {"type": "string"},
                },
            },
            "suggested_action": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "invitees": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
            },
        },
        "required": [
            "title",
            "summary",
            "affected_subsystems",
            "conflicts",
            "sources",
            "suggested_action",
        ],
    },
)


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_to_jsonable(o) for o in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


async def run_eve(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    seed: str | None = None,
    llm: LLMProvider | None = None,
    mcp: InProcessMCPClient | None = None,
) -> dict[str, Any] | None:
    """Run the agent loop; return the emitted insight dict (or None)."""
    provider = llm or get_provider()
    client = mcp or InProcessMCPClient()
    tools = [*_READ_TOOLS, _EMIT_TOOL]

    goal = seed or (
        "Review the most recent decisions, team messages, and spec documents. "
        "Find one high-impact change or a chatter-vs-spec conflict and emit it."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": goal}]
    nudged = False

    for turn in range(_MAX_TURNS):
        result = await provider.complete(
            tier=ModelTier.DIGEST,
            system=EVE_SYSTEM,
            messages=messages,
            tools=tools,
            max_tokens=2048,
            temperature=0.3,
        )
        if not result.tool_calls:
            # Agent ended with prose instead of emitting. Force a structured
            # emit once before giving up.
            if nudged:
                log.info("eve.no_tool_calls", turn=turn, stop=result.stop_reason)
                return None
            nudged = True
            if result.text:
                messages.append({"role": "assistant", "content": result.text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Now call emit_insight EXACTLY ONCE with your single best "
                        "insight, grounded in the evidence you gathered. Do not reply "
                        "with prose."
                    ),
                }
            )
            continue

        # Reconstruct the assistant turn (text + tool_use blocks).
        assistant: list[dict[str, Any]] = []
        if result.text:
            assistant.append({"type": "text", "text": result.text})
        assistant.extend(
            {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}
            for tc in result.tool_calls
        )
        messages.append({"role": "assistant", "content": assistant})

        tool_results: list[dict[str, Any]] = []
        for tc in result.tool_calls:
            if tc.name == "emit_insight":
                log.info("eve.emitted", turn=turn, title=tc.input.get("title"))
                return tc.input
            try:
                out = await client.call(tc.name, session, {**tc.input, "project_id": project_id})
                content = json.dumps(_to_jsonable(out))[:6000]
            except Exception as exc:  # noqa: BLE001
                log.warning("eve.tool_error", tool=tc.name, error=str(exc))
                content = json.dumps({"error": str(exc)})
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tc.id, "content": content},
            )
        messages.append({"role": "user", "content": tool_results})

    log.info("eve.max_turns_reached")
    return None
