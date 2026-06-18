"""Eve, the proactive insight agent: a native tool-use loop (<=8 turns) that
searches messages/docs/signals, then emits one grounded cross-functional insight."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.agent_tools.client import InProcessToolClient
from evercurrent.insights.serialization import to_jsonable
from evercurrent.insights.tools import EMIT_TOOL, READ_TOOLS
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

_MAX_TURNS = 8
_MAX_TOKENS = 2048


@dataclass
class EveRun:
    insight: dict[str, Any] | None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)

    @property
    def searched(self) -> bool:
        read_names = {t.name for t in READ_TOOLS}
        return any(name in read_names for name in self.tool_calls)


_TOOL_RESULT_CHAR_CAP = 6000
_PROMPT_PKG = "evercurrent.insights.prompts"


def _system_prompt() -> str:
    return resources.files(_PROMPT_PKG).joinpath("system.txt").read_text(encoding="utf-8")


def _as_evidence(tool_name: str, out: Any) -> list[dict[str, Any]]:
    """Normalize a search tool's output into insight sources, so Eve always has
    grounding even if the model omits `sources` in emit_insight."""
    if isinstance(out, list):
        items = out
    elif isinstance(out, dict):
        items = out.get("results") or out.get("messages") or out.get("signals") or []
    else:
        items = []
    kind = "doc" if tool_name == "search_documents" else "slack"
    evidence: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        snippet = (
            item.get("snippet") or item.get("text") or item.get("summary") or item.get("body") or ""
        )
        if not snippet:
            continue
        evidence.append(
            {
                "kind": kind,
                "channel": item.get("channel"),
                "author": item.get("author") or item.get("author_display_name"),
                "snippet": str(snippet)[:300],
                "ts": item.get("ts") or item.get("external_id") or item.get("posted_at"),
            },
        )
    return evidence


async def run_eve(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    seed: str | None = None,
    llm: LLMProvider | None = None,
    tool_client: InProcessToolClient | None = None,
) -> EveRun:
    provider = llm or get_provider()
    client = tool_client or InProcessToolClient()
    tools = [*READ_TOOLS, EMIT_TOOL]
    system = _system_prompt()

    goal = seed or (
        "Review the most recent decisions, team messages, and spec documents. "
        "Find one high-impact change or a chatter-vs-spec conflict and emit it."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": goal}]
    nudged = False
    evidence: list[dict[str, Any]] = []
    tool_calls: list[str] = []

    for turn in range(_MAX_TURNS):
        result = await provider.complete(
            tier=ModelTier.DIGEST,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=_MAX_TOKENS,
            temperature=0.3,
        )
        if not result.tool_calls:
            if nudged:
                log.info("eve.no_tool_calls", turn=turn, stop=result.stop_reason)
                return EveRun(insight=None, evidence=evidence, tool_calls=tool_calls)
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
                emitted = dict(tc.input)
                if not emitted.get("sources") and evidence:
                    emitted["sources"] = evidence[:3]
                log.info(
                    "eve.emitted",
                    turn=turn,
                    title=emitted.get("title"),
                    confidence=emitted.get("confidence"),
                    searched=bool(tool_calls),
                )
                return EveRun(insight=emitted, evidence=evidence, tool_calls=tool_calls)
            tool_calls.append(tc.name)
            try:
                out = await client.call(tc.name, session, {**tc.input, "project_id": project_id})
                jsonable = to_jsonable(out)
                evidence.extend(_as_evidence(tc.name, jsonable))
                content = json.dumps(jsonable)[:_TOOL_RESULT_CHAR_CAP]
            except Exception as exc:  # noqa: BLE001
                log.warning("eve.tool_error", tool=tc.name, error=str(exc))
                content = json.dumps({"error": str(exc)})
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tc.id, "content": content},
            )
        messages.append({"role": "user", "content": tool_results})

    log.info("eve.max_turns_reached")
    return EveRun(insight=None, evidence=evidence, tool_calls=tool_calls)
