from __future__ import annotations

import json
import uuid
from importlib import resources
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.eve.serialization import to_jsonable
from evercurrent.eve.tools import EMIT_TOOL, READ_TOOLS
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier
from evercurrent.mcp.client import InProcessMCPClient

log = structlog.get_logger(__name__)

_MAX_TURNS = 8
_MAX_TOKENS = 2048
_TOOL_RESULT_CHAR_CAP = 6000
_PROMPT_PKG = "evercurrent.eve.prompts"


def _system_prompt() -> str:
    return resources.files(_PROMPT_PKG).joinpath("system.txt").read_text(encoding="utf-8")


async def run_eve(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    seed: str | None = None,
    llm: LLMProvider | None = None,
    mcp: InProcessMCPClient | None = None,
) -> dict[str, Any] | None:
    provider = llm or get_provider()
    client = mcp or InProcessMCPClient()
    tools = [*READ_TOOLS, EMIT_TOOL]
    system = _system_prompt()

    goal = seed or (
        "Review the most recent decisions, team messages, and spec documents. "
        "Find one high-impact change or a chatter-vs-spec conflict and emit it."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": goal}]
    nudged = False

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
                content = json.dumps(to_jsonable(out))[:_TOOL_RESULT_CHAR_CAP]
            except Exception as exc:  # noqa: BLE001
                log.warning("eve.tool_error", tool=tc.name, error=str(exc))
                content = json.dumps({"error": str(exc)})
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tc.id, "content": content},
            )
        messages.append({"role": "user", "content": tool_results})

    log.info("eve.max_turns_reached")
    return None
