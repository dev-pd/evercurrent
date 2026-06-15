from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic
import structlog
from anthropic import AsyncAnthropic

from evercurrent.config import get_settings
from evercurrent.llm.metrics import record_llm_usage
from evercurrent.llm.tiering import ModelTier, model_for

log = structlog.get_logger(__name__)

_HTTP_SERVER_ERROR_THRESHOLD = 500
_RETRY_ATTEMPTS = 4


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CompletionResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        tier: ModelTier,
        system: str,
        messages: Sequence[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.2,
        tools: Sequence[ToolSpec] | None = None,
    ) -> CompletionResult: ...

    async def complete_json(
        self,
        *,
        tier: ModelTier,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> dict[str, Any] | list[Any]: ...

    def stream(
        self,
        *,
        tier: ModelTier,
        system: str,
        messages: Sequence[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.4,
        tools: Sequence[ToolSpec] | None = None,
    ) -> AsyncIterator[dict[str, Any]]: ...


def _is_retryable(exc: BaseException) -> bool:
    transient = (
        anthropic.APIConnectionError,
        anthropic.APITimeoutError,
        anthropic.RateLimitError,
    )
    if isinstance(exc, transient):
        return True
    return (
        isinstance(exc, anthropic.APIStatusError)
        and exc.status_code >= _HTTP_SERVER_ERROR_THRESHOLD
    )


class AnthropicProvider:
    def __init__(self, *, client: AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        if client is None:
            if not settings.anthropic_api_key:
                msg = "ANTHROPIC_API_KEY is not set; cannot construct AnthropicProvider."
                raise RuntimeError(msg)
            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._client = client

    async def _retrying_create(self, **kwargs: Any) -> anthropic.types.Message:
        last_exc: BaseException = RuntimeError("no attempts made")
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                return await self._client.messages.create(**kwargs)
            except anthropic.AnthropicError as exc:
                last_exc = exc
                if not _is_retryable(exc):
                    raise
                wait_s = min(0.5 * (2**attempt), 8.0)
                log.warning(
                    "llm.retry",
                    attempt=attempt + 1,
                    wait_s=wait_s,
                    exc_type=type(exc).__name__,
                )
                await asyncio.sleep(wait_s)
        raise last_exc

    async def complete(
        self,
        *,
        tier: ModelTier,
        system: str,
        messages: Sequence[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.2,
        tools: Sequence[ToolSpec] | None = None,
    ) -> CompletionResult:
        model = model_for(tier)
        started = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]
        resp = await self._retrying_create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        input=dict(getattr(block, "input", {}) or {}),
                    ),
                )

        result = CompletionResult(
            text="".join(text_parts),
            model=model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason,
        )
        log.info(
            "llm.complete",
            tier=tier.value,
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
            stop_reason=result.stop_reason,
        )
        record_llm_usage(model, tier.value, result.input_tokens, result.output_tokens)
        return result

    async def complete_json(
        self,
        *,
        tier: ModelTier,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> dict[str, Any] | list[Any]:
        json_instruction = (
            "\n\nReturn ONLY valid JSON. No prose, no markdown fences, no commentary."
        )
        result = await self.complete(
            tier=tier,
            system=system + json_instruction,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = result.text.strip()
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        return json.loads(text)

    async def stream(
        self,
        *,
        tier: ModelTier,
        system: str,
        messages: Sequence[dict[str, Any]],
        max_tokens: int = 1024,
        temperature: float = 0.4,
        tools: Sequence[ToolSpec] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        model = model_for(tier)
        kwargs: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                yield _serialise_stream_event(event, model)


def _serialise_stream_event(event: Any, model: str) -> dict[str, Any]:  # noqa: PLR0911
    etype = event.type
    if etype == "text":
        return {"type": "text_delta", "text": event.text, "model": model}
    if etype == "input_json":
        return {"type": "tool_input_delta", "partial_json": event.partial_json}
    if etype == "content_block_start":
        block = event.content_block
        if block.type == "tool_use":
            return {"type": "tool_use_start", "id": block.id, "name": block.name}
        return {"type": "content_block_start", "block_type": block.type}
    if etype == "content_block_stop":
        return {"type": "content_block_stop"}
    if etype == "message_stop":
        return {"type": "message_stop"}
    return {"type": etype}


_provider_singleton: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider_singleton  # noqa: PLW0603
    provider = _provider_singleton
    if provider is None:
        provider = AnthropicProvider()
        _provider_singleton = provider
    return provider


def set_provider(provider: LLMProvider) -> None:
    global _provider_singleton  # noqa: PLW0603
    _provider_singleton = provider
