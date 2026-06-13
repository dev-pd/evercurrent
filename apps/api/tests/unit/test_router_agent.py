from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from evercurrent.routing.router_agent import classify
from evercurrent.routing.schemas import RouterDecision


class _FakeLLM:
    def __init__(self, responses: list[Any | Exception | Callable[[], Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def complete_json(self, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("no scripted response left")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        if callable(nxt):
            return nxt()
        return nxt

    async def complete(self, **_kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError

    def stream(
        self,
        **_kwargs: Any,
    ) -> Awaitable[Any]:  # pragma: no cover - unused
        raise NotImplementedError


def _happy_payload() -> dict[str, Any]:
    return {
        "topic": "thermal_margin",
        "urgency": "high",
        "entities": ["ECO-178"],
        "affected_roles": ["mech", "ee"],
        "should_create_card": True,
        "card_kind": "decision",
        "card_summary": "Switch to AlumWest to recover thermal margin.",
        "confidence": 0.82,
    }


@pytest.mark.asyncio
async def test_classify_happy_path_returns_router_decision() -> None:
    llm = _FakeLLM([_happy_payload()])

    decision = await classify(
        llm=llm,
        message_text="Going with AlumWest, thermal margin is the gate.",
        channel="mech-design",
        author_display_name="Lin",
        author_role="mech",
        thread_parent_text=None,
        project_phase="DVT",
    )

    assert isinstance(decision, RouterDecision)
    assert decision.topic == "thermal_margin"
    assert decision.urgency == "high"
    assert decision.should_create_card is True
    assert decision.card_kind == "decision"
    assert decision.confidence == pytest.approx(0.82)
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_classify_retries_once_on_validation_error() -> None:
    invalid = {
        "topic": "thermal_margin",
        "urgency": "high",
        "entities": [],
        "affected_roles": [],
        "should_create_card": True,
        "card_kind": None,
        "card_summary": None,
        "confidence": 0.7,
    }
    llm = _FakeLLM([invalid, _happy_payload()])

    decision = await classify(
        llm=llm,
        message_text="Switching to AlumWest",
        channel="mech-design",
        author_display_name="Lin",
        author_role="mech",
        thread_parent_text=None,
        project_phase="DVT",
    )

    assert decision.should_create_card is True
    assert decision.card_kind == "decision"
    assert len(llm.calls) == 2
    second_prompt = llm.calls[1]["prompt"]
    assert "previous response did not match" in second_prompt


@pytest.mark.asyncio
async def test_classify_falls_back_when_retry_also_fails() -> None:
    invalid = {
        "urgency": "high",
    }
    llm = _FakeLLM([invalid, invalid])

    decision = await classify(
        llm=llm,
        message_text="garbled",
        channel="random",
        author_display_name="bot",
        author_role="member",
        thread_parent_text=None,
        project_phase="EVT",
    )

    assert decision.topic is None
    assert decision.urgency == "normal"
    assert decision.should_create_card is False
    assert decision.confidence == 0.0
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_classify_thread_parent_rendered_into_prompt() -> None:
    llm = _FakeLLM([_happy_payload()])
    parent = "Original message about ECO-178 sign-off."

    await classify(
        llm=llm,
        message_text="looks fine to me",
        channel="mech-design",
        author_display_name="Mei",
        author_role="em",
        thread_parent_text=parent,
        project_phase="DVT",
    )

    prompt = llm.calls[0]["prompt"]
    assert parent in prompt
    assert "Thread parent" in prompt


@pytest.mark.asyncio
async def test_classify_uses_tagging_tier() -> None:
    llm = _FakeLLM([_happy_payload()])
    await classify(
        llm=llm,
        message_text="x",
        channel="c",
        author_display_name="a",
        author_role="member",
        thread_parent_text=None,
        project_phase="EVT",
    )
    assert llm.calls[0]["tier"].value == "tagging"
