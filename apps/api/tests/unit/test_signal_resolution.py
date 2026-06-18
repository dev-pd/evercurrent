from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from evercurrent.signals.resolution import message_resolves_signal


class _FakeLLM:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def complete_json(self, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def complete(self, **_kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError

    def stream(self, **_kwargs: Any) -> AsyncIterator[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError


async def test_resolves_when_the_model_says_the_message_closes_the_signal() -> None:
    llm = _FakeLLM({"resolves": True, "reason": "team confirmed the alloy switch"})
    result = await message_resolves_signal(
        llm,
        kind="decision",
        summary="Pick the chassis alloy",
        body="Thermal margin slipped; choosing between AlumWest and the incumbent.",
        message_text="Final call: we're going with AlumWest.",
    )
    assert result is True
    assert llm.calls[0]["temperature"] == 0.0


async def test_keeps_open_when_the_model_says_it_does_not_resolve() -> None:
    llm = _FakeLLM({"resolves": False, "reason": "still debating cost"})
    result = await message_resolves_signal(
        llm,
        kind="risk",
        summary="Thermal margin risk",
        body="May not clear sign-off.",
        message_text="What does AlumWest do to unit cost?",
    )
    assert result is False


async def test_keeps_open_on_schema_drift() -> None:
    llm = _FakeLLM({"unexpected": "shape"})
    result = await message_resolves_signal(
        llm,
        kind="question",
        summary="q",
        body="body text here",
        message_text="...",
    )
    assert result is False


async def test_keeps_open_when_the_llm_errors() -> None:
    llm = _FakeLLM(RuntimeError("boom"))
    result = await message_resolves_signal(
        llm,
        kind="decision",
        summary="s",
        body="body text here",
        message_text="...",
    )
    assert result is False
