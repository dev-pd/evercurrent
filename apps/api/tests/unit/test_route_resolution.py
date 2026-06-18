from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

import evercurrent.jobs.tasks.route_message as rm


async def test_resolves_open_signal_when_the_check_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = uuid.uuid4()
    sig_id = uuid.uuid4()
    project_id = uuid.uuid4()
    message_id = uuid.uuid4()

    async def fake_root(_session: Any, _message_id: uuid.UUID) -> uuid.UUID | None:
        return root

    async def fake_open(
        _session: Any,
        *,
        thread_root_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        assert thread_root_id == root
        return [
            {
                "id": sig_id,
                "kind": "risk",
                "summary": "thermal risk",
                "body": "body",
                "project_id": project_id,
            },
        ]

    set_calls: list[tuple[uuid.UUID, str, uuid.UUID | None]] = []

    async def fake_set(
        _session: Any,
        *,
        signal_id: uuid.UUID,
        status: str,
        resolving_message_id: uuid.UUID | None = None,
    ) -> bool:
        set_calls.append((signal_id, status, resolving_message_id))
        return True

    async def fake_check(_llm: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(rm, "thread_root_for_message", fake_root)
    monkeypatch.setattr(rm.signals_repo, "open_signals_in_thread", fake_open)
    monkeypatch.setattr(rm.signals_repo, "set_status", fake_set)
    monkeypatch.setattr(rm, "message_resolves_signal", fake_check)

    resolved = await rm._resolve_thread_signals(
        AsyncMock(),
        AsyncMock(),
        message_id=message_id,
        message_text="resolved!",
    )

    assert [s["id"] for s in resolved] == [sig_id]
    assert set_calls == [(sig_id, "resolved", message_id)]


async def test_skips_entirely_when_message_has_no_thread_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_calls = {"n": 0}

    async def fake_root(_session: Any, _message_id: uuid.UUID) -> uuid.UUID | None:
        return None

    async def fake_open(_session: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        open_calls["n"] += 1
        return []

    monkeypatch.setattr(rm, "thread_root_for_message", fake_root)
    monkeypatch.setattr(rm.signals_repo, "open_signals_in_thread", fake_open)

    resolved = await rm._resolve_thread_signals(
        AsyncMock(),
        AsyncMock(),
        message_id=uuid.uuid4(),
        message_text="standalone",
    )

    assert resolved == []
    assert open_calls["n"] == 0


async def test_keeps_signal_open_when_the_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = uuid.uuid4()

    async def fake_root(_session: Any, _message_id: uuid.UUID) -> uuid.UUID | None:
        return root

    async def fake_open(_session: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": uuid.uuid4(),
                "kind": "decision",
                "summary": "s",
                "body": "body",
                "project_id": None,
            },
        ]

    set_calls = {"n": 0}

    async def fake_set(_session: Any, **_kwargs: Any) -> bool:
        set_calls["n"] += 1
        return True

    async def fake_check(_llm: Any, **_kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(rm, "thread_root_for_message", fake_root)
    monkeypatch.setattr(rm.signals_repo, "open_signals_in_thread", fake_open)
    monkeypatch.setattr(rm.signals_repo, "set_status", fake_set)
    monkeypatch.setattr(rm, "message_resolves_signal", fake_check)

    resolved = await rm._resolve_thread_signals(
        AsyncMock(),
        AsyncMock(),
        message_id=uuid.uuid4(),
        message_text="just discussing",
    )

    assert resolved == []
    assert set_calls["n"] == 0
