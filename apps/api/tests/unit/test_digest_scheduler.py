from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

import evercurrent.digest.digest_generator as agent_mod
import evercurrent.digest.repository as repo_mod
from evercurrent.digest.schemas import DigestRecord, MemberProfile, ProjectSnapshot


async def test_digest_idempotent_on_same_member_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    existing = DigestRecord(
        id=uuid.uuid4(),
        org_id=org_id,
        project_member_id=member_id,
        day_index=3,
        phase="DVT",
        content_md="## Top priority\n- existing",
        card_ids=[],
        message_ids=[],
        generated_at=dt.datetime(2026, 6, 7, 8, 1, tzinfo=dt.UTC),
    )

    get_calls = {"n": 0}

    async def fake_get(
        _session: Any,
        *,
        project_member_id: uuid.UUID,
        day_index: int,
    ) -> DigestRecord | None:
        get_calls["n"] += 1
        assert project_member_id == member_id
        assert day_index == 3
        return existing

    monkeypatch.setattr(repo_mod, "get_for_member_day", fake_get)

    llm = AsyncMock()

    result = await agent_mod.generate_digest(
        AsyncMock(),
        llm,
        project_member_id=member_id,
        day_index=3,
        phase="DVT",
        force=False,
    )

    assert result == existing
    assert get_calls["n"] == 1
    llm.complete_json.assert_not_called()


async def test_force_regen_replaces_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    new_digest = DigestRecord(
        id=uuid.uuid4(),
        org_id=org_id,
        project_member_id=member_id,
        day_index=3,
        phase="DVT",
        content_md="## Top priority\n- fresh",
        card_ids=[],
        message_ids=[],
        generated_at=dt.datetime(2026, 6, 7, 8, 4, tzinfo=dt.UTC),
    )

    async def fake_get(*_args: Any, **_kwargs: Any) -> DigestRecord | None:
        msg = "force=True must skip idempotency check"
        raise AssertionError(msg)

    async def fake_load_profile(
        _session: Any,
        _mid: uuid.UUID,
    ) -> tuple[Any, uuid.UUID]:
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

    async def fake_load_project(*_args: Any, **_kwargs: Any) -> Any:
        return ProjectSnapshot(
            project_id=uuid.UUID(int=0),
            name="Test",
            current_phase="DVT",
            phase_concerns=[],
        )

    async def fake_top(*_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    async def fake_open_cards(*_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    async def fake_recent(*_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    async def fake_upsert(*_args: Any, **kwargs: Any) -> DigestRecord:
        return new_digest.model_copy(update={"content_md": kwargs["content_md"]})

    monkeypatch.setattr(repo_mod, "get_for_member_day", fake_get)
    monkeypatch.setattr(repo_mod, "top_scored_items_for_member", fake_top)
    monkeypatch.setattr(repo_mod, "open_cards_for_member_subsystems", fake_open_cards)
    monkeypatch.setattr(repo_mod, "list_recent_for_member", fake_recent)
    monkeypatch.setattr(repo_mod, "upsert_digest", fake_upsert)
    monkeypatch.setattr(repo_mod, "load_member_profile", fake_load_profile)
    monkeypatch.setattr(repo_mod, "latest_project_id_for_org", fake_resolve_project_id)
    monkeypatch.setattr(repo_mod, "load_project_snapshot", fake_load_project)

    llm = AsyncMock()
    llm.complete_json = AsyncMock(
        return_value={
            "content_md": "## Top priority\n- fresh briefing for chassis owner",
            "card_ids": [],
            "message_ids": [],
            "section_buckets": {"top_priority": [], "watch_outs": [], "fyi": []},
        },
    )

    result = await agent_mod.generate_digest(
        AsyncMock(),
        llm,
        project_member_id=member_id,
        day_index=3,
        phase="DVT",
        force=True,
    )

    assert result.day_index == 3
    assert "fresh" in result.content_md
    llm.complete_json.assert_awaited_once()
