"""Agent runner: multi-turn tool-use loop with bounded iterations."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from evercurrent.agent.tools import TOOL_SPECS, ToolContext, dispatch_tool
from evercurrent.db.repositories import UserRepository
from evercurrent.db.session import session_scope
from evercurrent.llm.client import LLMProvider, get_provider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

MAX_ITERATIONS = 10
SYSTEM_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "system.txt").read_text()


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


async def _render_system(user_id: uuid.UUID | None) -> str:
    if user_id is None:
        return SYSTEM_PROMPT_TEMPLATE.format(
            user_name="anonymous",
            user_role="engineer",
            owned_subsystems="[]",
        )
    async with session_scope() as session:
        user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        return SYSTEM_PROMPT_TEMPLATE.format(
            user_name="anonymous",
            user_role="engineer",
            owned_subsystems="[]",
        )
    return SYSTEM_PROMPT_TEMPLATE.format(
        user_name=user.display_name,
        user_role=user.role.value,
        owned_subsystems=", ".join(user.owned_subsystems) or "n/a",
    )


async def run_agent(
    *,
    query: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    provider: LLMProvider | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AsyncIterator[AgentEvent]:
    """Yield AgentEvent objects as the agent thinks + uses tools."""
    llm = provider or get_provider()
    ctx = ToolContext(project_id=project_id, user_id=user_id)
    system = await _render_system(user_id)
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    for iteration in range(max_iterations):
        result = await llm.complete(
            tier=ModelTier.AGENT,
            system=system,
            messages=messages,
            max_tokens=2048,
            temperature=0.4,
            tools=TOOL_SPECS,
        )
        if result.text:
            yield AgentEvent(type="text_delta", payload={"text": result.text})

        if not result.tool_calls:
            yield AgentEvent(type="done", payload={"iterations": iteration + 1})
            return

        # Echo the assistant turn so the next call sees its own tool_use blocks.
        assistant_content: list[dict[str, Any]] = []
        if result.text:
            assistant_content.append({"type": "text", "text": result.text})
        assistant_content.extend(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
            for call in result.tool_calls
        )
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results: list[dict[str, Any]] = []
        for call in result.tool_calls:
            yield AgentEvent(
                type="tool_use_start",
                payload={"id": call.id, "name": call.name, "input": call.input},
            )
            payload = await dispatch_tool(call.name, call.input, ctx)
            yield AgentEvent(
                type="tool_use_result",
                payload={"id": call.id, "name": call.name, "result": payload},
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(payload),
                },
            )
        messages.append({"role": "user", "content": tool_results})

    yield AgentEvent(
        type="done",
        payload={"iterations": max_iterations, "truncated": True},
    )
