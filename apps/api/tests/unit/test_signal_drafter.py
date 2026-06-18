from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

import evercurrent.signals.repository as repo_mod
import evercurrent.signals.signal_drafter as builder_mod
from evercurrent.agent_tools.schemas import MessageRef, ThreadContext


class _FakeLLM:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def complete_json(self, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self.calls.append(kwargs)
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    async def complete(self, **_kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError

    def stream(self, **_kwargs: Any) -> AsyncIterator[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError


def _happy_draft() -> dict[str, Any]:
    return {
        "summary": "Switch to AlumWest to recover thermal margin on ECO-178.",
        "body": (
            "After the supplier flagged a thermal margin slip, the team "
            "agreed to switch to the AlumWest alloy. This adds 12C of "
            "headroom and clears the ECO-178 sign-off path for next week."
        ),
        "affected_subsystems": ["thermal"],
        "confidence": 0.82,
        "decided_at": None,
    }


@pytest.fixture
def now_utc() -> dt.datetime:
    return dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC)


@pytest.fixture
def fake_session() -> AsyncMock:
    session = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def tool_client_with_thread(now_utc: dt.datetime) -> MagicMock:
    root_id = uuid.uuid4()
    reply_id = uuid.uuid4()
    root = MessageRef(
        id=root_id,
        channel="mech-design",
        author="Mei",
        text="ECO-178 thermal margin is tight.",
        posted_at=now_utc,
    )
    reply = MessageRef(
        id=reply_id,
        channel="mech-design",
        author="Lin",
        text="Switching to AlumWest then.",
        posted_at=now_utc,
    )
    client = MagicMock()
    client.call = AsyncMock(return_value=ThreadContext(root=root, replies=[reply]))
    client._root_id = root_id  # type: ignore[attr-defined]
    client._reply_id = reply_id  # type: ignore[attr-defined]
    return client


def _patch_repo(
    monkeypatch: pytest.MonkeyPatch,
    *,
    existing_first: dict[str, Any] | None,
    existing_after_insert: dict[str, Any] | None = None,
    insert_signal_returns: uuid.UUID | None = None,
    insert_signal_raises: Exception | None = None,
) -> dict[str, list[Any]]:
    captured: dict[str, list[Any]] = {
        "existing_calls": [],
        "insert_calls": [],
        "source_calls": [],
    }
    existing_responses = [existing_first, existing_after_insert]

    async def fake_get_existing(*_args: Any, **kwargs: Any) -> dict[str, Any] | None:
        captured["existing_calls"].append(kwargs)
        if not existing_responses:
            return None
        return existing_responses.pop(0)

    async def fake_insert_signal(*_args: Any, **kwargs: Any) -> uuid.UUID:
        captured["insert_calls"].append(kwargs)
        if insert_signal_raises is not None:
            raise insert_signal_raises
        if insert_signal_returns is None:
            return uuid.uuid4()
        return insert_signal_returns

    async def fake_add_sources(*_args: Any, **kwargs: Any) -> None:
        captured["source_calls"].append(kwargs)

    async def fake_affected_roles(*_args: Any, **_kwargs: Any) -> list[str]:
        return ["supply"]

    monkeypatch.setattr(repo_mod, "get_existing_signal", fake_get_existing)
    monkeypatch.setattr(repo_mod, "insert_signal", fake_insert_signal)
    monkeypatch.setattr(repo_mod, "add_signal_sources", fake_add_sources)
    monkeypatch.setattr(repo_mod, "message_affected_roles", fake_affected_roles)
    return captured


def _patch_meta_and_project(
    monkeypatch: pytest.MonkeyPatch,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None,
    message_text: str = "Switching to AlumWest.",
) -> None:
    async def fake_load_message_meta(
        _session: Any,
        _message_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        return {
            "id": _message_id,
            "org_id": str(org_id),
            "project_id": str(project_id) if project_id else None,
            "channel": "mech-design",
            "text": message_text,
            "author_display_name": "Lin",
            "posted_at": dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
        }

    async def fake_resolve_project_context(
        _session: Any,
        _project_id: uuid.UUID | None,
    ) -> tuple[str, list[str]]:
        return "DVT", ["thermal", "powertrain"]

    monkeypatch.setattr(
        builder_mod,
        "_load_message_meta",
        fake_load_message_meta,
    )
    monkeypatch.setattr(
        repo_mod,
        "project_phase_and_subsystems",
        fake_resolve_project_context,
    )


@pytest.mark.asyncio
async def test_build_signal_happy_path_writes_signal_and_sources(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncMock,
    tool_client_with_thread: MagicMock,
) -> None:
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    message_id = uuid.uuid4()
    signal_id = uuid.uuid4()

    _patch_meta_and_project(
        monkeypatch,
        org_id=org_id,
        project_id=project_id,
    )
    captured = _patch_repo(
        monkeypatch,
        existing_first=None,
        insert_signal_returns=signal_id,
    )

    llm = _FakeLLM([_happy_draft()])

    result = await builder_mod.build_signal(
        fake_session,
        llm,
        message_id=message_id,
        kind="decision",
        summary_hint="Switch alloy",
        tool_client=tool_client_with_thread,
    )

    assert result["signal_id"] == signal_id
    assert result["existing"] is False
    assert len(llm.calls) == 1
    assert len(captured["insert_calls"]) == 1
    insert_kwargs = captured["insert_calls"][0]
    assert insert_kwargs["org_id"] == org_id
    assert insert_kwargs["project_id"] == project_id
    assert insert_kwargs["kind"] == "decision"
    assert insert_kwargs["triggering_message_id"] == message_id

    assert len(captured["source_calls"]) == 1
    refs = captured["source_calls"][0]["refs"]
    assert ("message", message_id) in refs
    assert ("message", tool_client_with_thread._root_id) in refs
    assert ("message", tool_client_with_thread._reply_id) in refs


@pytest.mark.asyncio
async def test_build_signal_idempotent_when_existing(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncMock,
    tool_client_with_thread: MagicMock,
) -> None:
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    message_id = uuid.uuid4()
    signal_id = uuid.uuid4()

    captured = _patch_repo(
        monkeypatch,
        existing_first={
            "id": str(signal_id),
            "org_id": str(org_id),
            "project_id": str(project_id),
            "kind": "decision",
            "summary": "already exists",
            "body": "...",
            "status": "open",
            "confidence": 0.7,
            "decided_at": None,
            "affected_subsystems": [],
            "created_at": dt.datetime(2026, 6, 7, tzinfo=dt.UTC),
            "updated_at": dt.datetime(2026, 6, 7, tzinfo=dt.UTC),
        },
    )

    llm = _FakeLLM([])

    result = await builder_mod.build_signal(
        fake_session,
        llm,
        message_id=message_id,
        kind="decision",
        summary_hint="ignored",
        tool_client=tool_client_with_thread,
    )

    assert result["signal_id"] == signal_id
    assert result["existing"] is True
    assert len(llm.calls) == 0
    assert len(captured["insert_calls"]) == 0
    assert len(captured["source_calls"]) == 0
    tool_client_with_thread.call.assert_not_called()


@pytest.mark.asyncio
async def test_build_signal_handles_integrity_error_race(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncMock,
    tool_client_with_thread: MagicMock,
) -> None:
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    message_id = uuid.uuid4()
    existing_signal_id = uuid.uuid4()

    _patch_meta_and_project(
        monkeypatch,
        org_id=org_id,
        project_id=project_id,
    )
    integrity_err = IntegrityError("INSERT", {}, Exception("dup"))
    captured = _patch_repo(
        monkeypatch,
        existing_first=None,
        existing_after_insert={
            "id": str(existing_signal_id),
            "org_id": str(org_id),
            "project_id": str(project_id),
            "kind": "decision",
            "summary": "race winner",
            "body": "...",
            "status": "open",
            "confidence": 0.7,
            "decided_at": None,
            "affected_subsystems": [],
            "created_at": dt.datetime(2026, 6, 7, tzinfo=dt.UTC),
            "updated_at": dt.datetime(2026, 6, 7, tzinfo=dt.UTC),
        },
        insert_signal_raises=integrity_err,
    )

    llm = _FakeLLM([_happy_draft()])

    result = await builder_mod.build_signal(
        fake_session,
        llm,
        message_id=message_id,
        kind="decision",
        summary_hint="race",
        tool_client=tool_client_with_thread,
    )

    assert result["signal_id"] == existing_signal_id
    assert result["existing"] is True
    assert len(captured["insert_calls"]) == 1
    fake_session.rollback.assert_awaited()
    assert len(captured["source_calls"]) == 0
