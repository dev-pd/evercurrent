from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

import evercurrent.digest.digest_generator as agent_mod
import evercurrent.digest.repository as repo_mod
from evercurrent.digest.schemas import (
    DigestRecord,
    MemberProfile,
    ProjectSnapshot,
    ScoredItem,
    SignalSummary,
)


def _scored_item(message_id: uuid.UUID, score: float) -> ScoredItem:
    return ScoredItem(
        message_id=message_id,
        score=score,
        topic="thermal",
        urgency="high",
        channel="mech-design",
        author="Mei",
        text="margin tight",
        posted_at=dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
    )


def _signal_summary(signal_id: uuid.UUID) -> SignalSummary:
    return SignalSummary(
        signal_id=signal_id,
        kind="risk",
        summary="Thermal margin slipping on ECO-178",
        status="open",
        affected_subsystems=["chassis"],
        updated_at=dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC),
    )


async def _patch_agent_context(
    monkeypatch: pytest.MonkeyPatch,
    *,
    member_id: uuid.UUID,
    org_id: uuid.UUID,
    scored: list[ScoredItem],
    signals: list[SignalSummary],
) -> None:
    async def fake_load_profile(
        _session: Any,
        _mid: uuid.UUID,
    ) -> tuple[MemberProfile, uuid.UUID]:
        return (
            MemberProfile(
                project_member_id=member_id,
                display_name="Mei",
                role="mech",
                timezone="UTC",
                owned_subsystems=["chassis"],
                topic_weights={},
            ),
            org_id,
        )

    async def fake_resolve_project_id(*_args: Any, **_kwargs: Any) -> uuid.UUID | None:
        return None

    async def fake_load_project(*_args: Any, **_kwargs: Any) -> ProjectSnapshot:
        return ProjectSnapshot(
            project_id=uuid.UUID(int=0),
            name="Test",
            current_phase="DVT",
            phase_concerns=["thermal"],
        )

    async def fake_top(
        _session: Any,
        *,
        project_member_id: uuid.UUID,
        limit: int,
    ) -> list[ScoredItem]:
        assert project_member_id == member_id
        assert limit == 20
        return scored

    async def fake_open_signals(*_args: Any, **_kwargs: Any) -> list[SignalSummary]:
        return signals

    async def fake_recent(*_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    async def fake_get_for_member_day(*_args: Any, **_kwargs: Any) -> DigestRecord | None:
        return None

    monkeypatch.setattr(repo_mod, "load_member_profile", fake_load_profile)
    monkeypatch.setattr(repo_mod, "latest_project_id_for_org", fake_resolve_project_id)
    monkeypatch.setattr(repo_mod, "load_project_snapshot", fake_load_project)
    monkeypatch.setattr(repo_mod, "top_scored_items_for_member", fake_top)
    monkeypatch.setattr(repo_mod, "open_signals_for_member_subsystems", fake_open_signals)
    monkeypatch.setattr(repo_mod, "list_recent_for_member", fake_recent)
    monkeypatch.setattr(repo_mod, "get_for_member_day", fake_get_for_member_day)


async def test_persisted_row_has_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    signal_id = uuid.uuid4()

    await _patch_agent_context(
        monkeypatch,
        member_id=member_id,
        org_id=org_id,
        scored=[_scored_item(msg_id, 0.9)],
        signals=[_signal_summary(signal_id)],
    )

    captured_upsert: dict[str, Any] = {}

    async def fake_upsert(
        _session: Any,
        *,
        org_id: uuid.UUID,
        project_member_id: uuid.UUID,
        day_index: int,
        phase: str,
        content_md: str,
        signal_ids: list[uuid.UUID],
        message_ids: list[uuid.UUID],
    ) -> DigestRecord:
        captured_upsert.update(
            {
                "org_id": org_id,
                "project_member_id": project_member_id,
                "day_index": day_index,
                "phase": phase,
                "content_md": content_md,
                "signal_ids": signal_ids,
                "message_ids": message_ids,
            },
        )
        return DigestRecord(
            id=uuid.uuid4(),
            org_id=org_id,
            project_member_id=project_member_id,
            day_index=day_index,
            phase=phase,
            content_md=content_md,
            signal_ids=signal_ids,
            message_ids=message_ids,
            generated_at=dt.datetime(2026, 6, 7, 8, 0, tzinfo=dt.UTC),
        )

    monkeypatch.setattr(repo_mod, "upsert_digest", fake_upsert)

    llm = AsyncMock()
    llm.complete_json = AsyncMock(
        return_value={
            "content_md": (
                f"## Top priority\n- Thermal margin slipping [signal:{signal_id}] [msg:{msg_id}]"
            ),
            "signal_ids": [str(signal_id)],
            "message_ids": [str(msg_id)],
            "section_buckets": {
                "top_priority": [str(signal_id), str(msg_id)],
                "watch_outs": [],
                "fyi": [],
            },
        },
    )

    persisted = await agent_mod.generate_digest(
        AsyncMock(),
        llm,
        project_member_id=member_id,
        day_index=2,
        phase="DVT",
        force=False,
    )

    assert persisted is not None
    assert persisted.day_index == 2
    assert msg_id in persisted.message_ids
    assert signal_id in persisted.signal_ids
    assert captured_upsert["signal_ids"] == [signal_id]
    assert captured_upsert["message_ids"] == [msg_id]


async def test_hallucinated_citations_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    real_msg = uuid.uuid4()
    real_signal = uuid.uuid4()
    hallucinated_msg = uuid.uuid4()
    hallucinated_signal = uuid.uuid4()

    await _patch_agent_context(
        monkeypatch,
        member_id=member_id,
        org_id=org_id,
        scored=[_scored_item(real_msg, 0.7)],
        signals=[_signal_summary(real_signal)],
    )

    captured: dict[str, Any] = {}

    async def fake_upsert(_session: Any, **kwargs: Any) -> DigestRecord:
        captured.update(kwargs)
        return DigestRecord(
            id=uuid.uuid4(),
            org_id=kwargs["org_id"],
            project_member_id=kwargs["project_member_id"],
            day_index=kwargs["day_index"],
            phase=kwargs["phase"],
            content_md=kwargs["content_md"],
            signal_ids=kwargs["signal_ids"],
            message_ids=kwargs["message_ids"],
            generated_at=dt.datetime(2026, 6, 7, 8, 0, tzinfo=dt.UTC),
        )

    monkeypatch.setattr(repo_mod, "upsert_digest", fake_upsert)

    llm = AsyncMock()
    llm.complete_json = AsyncMock(
        return_value={
            "content_md": "## Top priority\n- something",
            "signal_ids": [str(real_signal), str(hallucinated_signal)],
            "message_ids": [str(real_msg), str(hallucinated_msg)],
            "section_buckets": {},
        },
    )

    await agent_mod.generate_digest(
        AsyncMock(),
        llm,
        project_member_id=member_id,
        day_index=1,
        phase="DVT",
        force=False,
    )

    assert captured["signal_ids"] == [real_signal]
    assert captured["message_ids"] == [real_msg]
