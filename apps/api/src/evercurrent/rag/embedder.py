"""Embedding port (EmbeddingProvider) + the Voyage adapter that batches text
into voyage-3-lite vectors. Swap the provider to change embedding backends."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

import structlog
import voyageai

from evercurrent.config import get_settings

log = structlog.get_logger(__name__)

_BATCH_SIZE = 128


class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class VoyageEmbedder:
    def __init__(self, *, model: str | None = None) -> None:
        settings = get_settings()
        if not settings.voyage_api_key:
            msg = "VOYAGE_API_KEY not set; cannot construct VoyageEmbedder."
            raise RuntimeError(msg)
        self._client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        self._model = model or settings.voyage_model
        self._dim = settings.voyage_embedding_dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, input_type="document")

    async def embed_query(self, text: str) -> list[float]:
        result = await self._embed([text], input_type="query")
        return result[0]

    async def _embed(
        self,
        texts: list[str],
        *,
        input_type: Literal["document", "query"],
    ) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response: Any = await self._with_retry(
                lambda b=batch: self._client.embed(
                    b,
                    model=self._model,
                    input_type=input_type,
                ),
            )
            out.extend(response.embeddings)
        return out

    @staticmethod
    async def _with_retry(coro_factory: Callable[[], Awaitable[Any]]) -> Any:
        attempts = 4
        for attempt in range(attempts):
            try:
                return await coro_factory()
            except Exception as exc:
                if attempt == attempts - 1:
                    raise
                wait_s = min(0.5 * (2**attempt), 8.0)
                log.warning(
                    "voyage.retry",
                    attempt=attempt + 1,
                    wait_s=wait_s,
                    exc_type=type(exc).__name__,
                )
                await asyncio.sleep(wait_s)
        msg = "unreachable"
        raise RuntimeError(msg)


_embedder_singleton: EmbeddingProvider | None = None


def get_embedder() -> EmbeddingProvider:
    global _embedder_singleton  # noqa: PLW0603
    instance = _embedder_singleton
    if instance is None:
        instance = VoyageEmbedder()
        _embedder_singleton = instance
    return instance


def set_embedder(embedder: EmbeddingProvider) -> None:
    global _embedder_singleton  # noqa: PLW0603
    _embedder_singleton = embedder
