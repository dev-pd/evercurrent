"""Unit test for `ingest_pdf_bytes` idempotency.

The Drive webhook will fire `change` events that don't actually change
the underlying file. We rely on UNIQUE `(source, external_id)` plus a
fast-path branch in the task to make a re-ingest a no-op rather than a
duplicate-row insert.

Strategy:

- Stub the embedder with a deterministic fake so we don't need Voyage.
- Stub `extract_blocks` to return a fixed list (no fitz dependency).
- Stub `session_scope` to return an in-memory recorder that captures
  the (source, external_id) of every "INSERT" into documents.

We then call `ingest_pdf_bytes` twice and assert the second call short-
circuits without adding a second document row.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest

from evercurrent.ingestion import tasks as ingest_tasks
from evercurrent.ingestion.pdf_extract import Block


class _FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[0.0] * 512 for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        _ = text
        return [0.0] * 512


class _DocRow:
    def __init__(self, *, source: str, external_id: str, **kwargs: Any) -> None:
        self.id = uuid.uuid4()
        self.source = source
        self.external_id = external_id
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Recorder:
    """Captures every document add + lookup, satisfies the async session API."""

    def __init__(self) -> None:
        self.documents: list[_DocRow] = []
        self.chunks_added = 0
        self.lookup_calls = 0
        self.delete_calls = 0
        # Pre-populate a single Project so _resolve_default_project succeeds.
        self.project_id = uuid.uuid4()

    def reset_per_session(self) -> None:
        self.lookup_calls = 0

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> Any:
        _ = stmt, args, kwargs
        self.lookup_calls += 1

        class _Row:
            def __init__(self, value: Any) -> None:
                self._value = value

            def __getitem__(self, idx: int) -> Any:
                _ = idx
                return self._value

        class _Result:
            def __init__(self, value: Any) -> None:
                self._value = value

            def scalar_one_or_none(self) -> Any:
                return self._value

            def first(self) -> Any:
                if self._value is None:
                    return None
                return _Row(self._value)

            def scalars(self) -> Any:
                value = self._value

                class _Scalars:
                    def all(self) -> list[Any]:
                        _ = self
                        return [value] if value is not None else []

                return _Scalars()

        call_index = self.lookup_calls
        if call_index == 1:
            # set_org_context — has no result we care about.
            return _Result(None)
        if call_index == 2:
            # _resolve_default_project: return a fake project row (raw SQL).
            return _Result(str(self.project_id))
        if call_index == 3:
            # _upsert_document SELECT — return the matching doc if exists.
            doc = self.documents[0] if self.documents else None
            return _Result(doc)
        # _replace_chunks SELECT — return existing chunks (none here).
        return _Result(None)

    def add(self, row: Any) -> None:
        if isinstance(row, _DocRow) or row.__class__.__name__ == "Document":
            # Coerce ORM Document instances into our fake shape.
            if not isinstance(row, _DocRow):
                row = _DocRow(
                    source=row.source,
                    external_id=row.external_id,
                    title=getattr(row, "title", "?"),
                )
            self.documents.append(row)
        elif row.__class__.__name__ == "DocumentChunk":
            self.chunks_added += 1

    async def flush(self) -> None:
        return

    async def delete(self, _row: Any) -> None:
        self.delete_calls += 1

    async def commit(self) -> None:
        return

    async def get(self, _model: Any, _id: Any) -> Any:
        return None


@asynccontextmanager
async def _fake_session_scope(recorder: _Recorder) -> Any:
    recorder.reset_per_session()
    yield recorder


@pytest.mark.asyncio
async def test_ingest_pdf_bytes_idempotent_by_external_id() -> None:
    recorder = _Recorder()
    fake_blocks = [Block(page=1, bbox=(0.0, 0.0, 100.0, 20.0), text="x" * 200)]
    fake_embedder = _FakeEmbedder()

    org_id = uuid.uuid4()
    source = "drive"
    external_id = "abc-123"

    with (
        patch.object(ingest_tasks, "extract_blocks", return_value=fake_blocks),
        patch.object(
            ingest_tasks,
            "session_scope",
            lambda: _fake_session_scope(recorder),
        ),
        patch.object(ingest_tasks, "publish_event", lambda *_a, **_k: None),
        patch.object(
            ingest_tasks,
            "classify_document",
            lambda **_k: _ImmediateNone(),
        ),
    ):
        result_first = await ingest_tasks.ingest_pdf_bytes(
            org_id=org_id,
            source=source,
            external_id=external_id,
            title="One",
            pdf_bytes=b"%PDF-1.4",
            embedder=fake_embedder,
        )
        result_second = await ingest_tasks.ingest_pdf_bytes(
            org_id=org_id,
            source=source,
            external_id=external_id,
            title="One",
            pdf_bytes=b"%PDF-1.4",
            embedder=fake_embedder,
        )

    assert result_first["chunks"] >= 1
    assert result_second.get("skipped") == "duplicate"
    # Exactly one document row was created.
    assert len(recorder.documents) == 1


class _ImmediateNone:
    """An awaitable that evaluates to None — `classify_document` is mocked."""

    def __await__(self):  # type: ignore[no-untyped-def]
        async def _none() -> None:
            return None

        return _none().__await__()
