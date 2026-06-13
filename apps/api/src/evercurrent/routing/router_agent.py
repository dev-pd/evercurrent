from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

import structlog
from pydantic import ValidationError

from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier
from evercurrent.routing.schemas import RouterDecision, fallback_decision

log = structlog.get_logger(__name__)


_PROMPT_PKG = "evercurrent.routing.prompts"


def _load_prompt(name: str) -> str:
    return resources.files(_PROMPT_PKG).joinpath(name).read_text(encoding="utf-8")


_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_IF_BLOCK_PATTERN = re.compile(
    r"\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}\n?(.*?)\{%\s*endif\s*%\}\n?",
    re.DOTALL,
)


def _render(template: str, context: dict[str, Any]) -> str:

    def _eval_if(match: re.Match[str]) -> str:
        name = match.group(1)
        body = match.group(2)
        value = context.get(name)
        if not value:
            return ""
        return body

    rendered = _IF_BLOCK_PATTERN.sub(_eval_if, template)

    def _eval_var(match: re.Match[str]) -> str:
        name = match.group(1)
        value = context.get(name)
        if value is None:
            return ""
        return str(value)

    return _VAR_PATTERN.sub(_eval_var, rendered)


def _build_user_prompt(
    *,
    message_text: str,
    channel: str,
    author_display_name: str,
    author_role: str,
    thread_parent_text: str | None,
    project_phase: str,
) -> str:
    template = _load_prompt("router_user.txt.j2")
    return _render(
        template,
        {
            "message_text": message_text,
            "channel": channel,
            "author_display_name": author_display_name,
            "author_role": author_role,
            "thread_parent_text": thread_parent_text or "",
            "project_phase": project_phase,
        },
    )


_RETRY_REMINDER = (
    "Your previous response did not match the RouterDecision schema. "
    "Re-emit it as a single JSON object with exactly these fields: "
    "topic (string or null), urgency (one of low|normal|high|critical), "
    "entities (array of strings), affected_roles (array of strings), "
    "should_create_card (bool), card_kind (decision|risk|question or null), "
    "card_summary (string or null), confidence (number 0..1). "
    "If should_create_card is false, card_kind AND card_summary MUST be null."
)


def _parse_decision(payload: Any) -> RouterDecision:
    if isinstance(payload, list):
        msg = "expected JSON object, got list"
        raise TypeError(msg)
    return RouterDecision.model_validate(payload)


async def _complete_json(
    llm: LLMProvider,
    *,
    system: str,
    prompt: str,
) -> dict[str, Any] | list[Any]:
    return await llm.complete_json(
        tier=ModelTier.TAGGING,
        system=system,
        prompt=prompt,
        max_tokens=512,
        temperature=0.0,
    )


async def classify(
    *,
    llm: LLMProvider,
    message_text: str,
    channel: str,
    author_display_name: str,
    author_role: str,
    thread_parent_text: str | None,
    project_phase: str,
) -> RouterDecision:
    system = _load_prompt("router_system.txt")
    user_prompt = _build_user_prompt(
        message_text=message_text,
        channel=channel,
        author_display_name=author_display_name,
        author_role=author_role,
        thread_parent_text=thread_parent_text,
        project_phase=project_phase,
    )

    try:
        payload = await _complete_json(llm, system=system, prompt=user_prompt)
        return _parse_decision(payload)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as first_exc:
        log.warning(
            "router.classify.retry",
            reason="schema_drift",
            error=str(first_exc),
        )

    retry_prompt = user_prompt + "\n\n" + _RETRY_REMINDER
    try:
        payload = await _complete_json(llm, system=system, prompt=retry_prompt)
        return _parse_decision(payload)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as second_exc:
        log.warning(
            "router.classify.fallback",
            reason="schema_drift_after_retry",
            error=str(second_exc),
        )
        return fallback_decision()
