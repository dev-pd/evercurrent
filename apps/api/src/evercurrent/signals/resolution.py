"""Conservative Haiku check: does a new in-thread message resolve an open
signal? Defaults to keep-open on any doubt, schema drift, or LLM error — a
false negative just leaves the signal open; a false positive hides live work."""

from __future__ import annotations

import json
from importlib import resources

import structlog
from pydantic import ValidationError

from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier
from evercurrent.signals.schemas import ResolveCheck

log = structlog.get_logger(__name__)

_PROMPT_PKG = "evercurrent.signals.prompts"


def _load_prompt(name: str) -> str:
    return resources.files(_PROMPT_PKG).joinpath(name).read_text(encoding="utf-8")


def _build_prompt(*, kind: str, summary: str, body: str, message_text: str) -> str:
    return (
        f"Open signal (kind: {kind}):\n"
        f"Summary: {summary}\n"
        f"Detail: {body}\n\n"
        f"New message in the same thread:\n"
        f"{message_text}\n\n"
        f"Does this new message resolve the signal above?"
    )


async def message_resolves_signal(
    llm: LLMProvider,
    *,
    kind: str,
    summary: str,
    body: str,
    message_text: str,
) -> bool:
    """True only when the message clearly closes the signal. Any failure to get
    a clean verdict returns False (keep-open)."""
    system = _load_prompt("resolve_check.txt")
    prompt = _build_prompt(
        kind=kind,
        summary=summary,
        body=body,
        message_text=message_text,
    )
    try:
        payload = await llm.complete_json(
            tier=ModelTier.TAGGING,
            system=system,
            prompt=prompt,
            max_tokens=256,
            temperature=0.0,
        )
        if isinstance(payload, list):
            msg = "expected JSON object, got list"
            raise TypeError(msg)  # noqa: TRY301
        return ResolveCheck.model_validate(payload).resolves
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as exc:
        log.warning("signals.resolve_check.parse_failed", error=str(exc))
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning("signals.resolve_check.llm_failed", error=str(exc))
        return False
