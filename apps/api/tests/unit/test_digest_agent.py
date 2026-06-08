"""Unit tests for `digest.agent.generate_digest`.

The agent mixes I/O (DB reads via the repository) and one Sonnet call.
We stub everything except the agent body so we can assert:

- the persisted row carries the citations the model emitted
- hallucinated UUIDs are dropped from the persisted row
- the top-N scored items query is the one the digest reads from
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

import evercurrent.digest.agent as agent_mod
import evercurrent.digest.repository as repo_mod
from evercurrent.digest.schemas import (
    CardSummary,
    MemberProfile,
    ProjectSnapshot,
    ScoredItem,
)
from evercurrent.domain.digests import Digest


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


def _card_summary(card_id: uuid.UUID) -> CardSummary:
    return CardSummary(
        card_id=card_id,
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
    cards: list[CardSummary],
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
        assert limit == 20  # locks the contract
        return scored

    async def fake_open_cards(*_args: Any, **_kwargs: Any) -> list[CardSummary]:
        return cards

    async def fake_recent(*_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    async def fake_get_for_member_day(*_args: Any, **_kwargs: Any) -> Digest | None:
        return None

    monkeypatch.setattr(agent_mod, "_load_member_profile", fake_load_profile)
    monkeypatch.setattr(
        agent_mod, "_resolve_project_id_for_member", fake_resolve_project_id,
    )
    monkeypatch.setattr(agent_mod, "_load_project_snapshot", fake_load_project)
    monkeypatch.setattr(repo_mod, "top_scored_items_for_member", fake_top)
    monkeypatch.setattr(repo_mod, "open_cards_for_member_subsystems", fake_open_cards)
    monkeypatch.setattr(repo_mod, "list_recent_for_member", fake_recent)
    monkeypatch.setattr(repo_mod, "get_for_member_day", fake_get_for_member_day)


async def test_persisted_row_has_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    card_id = uuid.uuid4()

    await _patch_agent_context(
        monkeypatch,
        member_id=member_id,
        org_id=org_id,
        scored=[_scored_item(msg_id, 0.9)],
        cards=[_card_summary(card_id)],
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
        card_ids: list[uuid.UUID],
        message_ids: list[uuid.UUID],
    ) -> Digest:
        captured_upsert.update(
            {
                "org_id": org_id,
                "project_member_id": project_member_id,
                "day_index": day_index,
                "phase": phase,
                "content_md": content_md,
                "card_ids": card_ids,
                "message_ids": message_ids,
            },
        )
        return Digest(
            id=uuid.uuid4(),
            org_id=org_id,
            project_member_id=project_member_id,
            day_index=day_index,
            phase=phase,
            content_md=content_md,
            card_ids=card_ids,
            message_ids=message_ids,
            generated_at=dt.datetime(2026, 6, 7, 8, 0, tzinfo=dt.UTC),
        )

    monkeypatch.setattr(repo_mod, "upsert_digest", fake_upsert)

    llm = AsyncMock()
    llm.complete_json = AsyncMock(
        return_value={
            "content_md": (
                "## Top priority\n"
                f"- Thermal margin slipping [card:{card_id}] [msg:{msg_id}]"
            ),
            "card_ids": [str(card_id)],
            "message_ids": [str(msg_id)],
            "section_buckets": {
                "top_priority": [str(card_id), str(msg_id)],
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

    assert persisted.day_index == 2
    assert msg_id in persisted.message_ids
    assert card_id in persisted.card_ids
    assert captured_upsert["card_ids"] == [card_id]
    assert captured_upsert["message_ids"] == [msg_id]


async def test_hallucinated_citations_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    real_msg = uuid.uuid4()
    real_card = uuid.uuid4()
    hallucinated_msg = uuid.uuid4()
    hallucinated_card = uuid.uuid4()

    await _patch_agent_context(
        monkeypatch,
        member_id=member_id,
        org_id=org_id,
        scored=[_scored_item(real_msg, 0.7)],
        cards=[_card_summary(real_card)],
    )

    captured: dict[str, Any] = {}

    async def fake_upsert(_session: Any, **kwargs: Any) -> Digest:
        captured.update(kwargs)
        return Digest(
            id=uuid.uuid4(),
            org_id=kwargs["org_id"],
            project_member_id=kwargs["project_member_id"],
            day_index=kwargs["day_index"],
            phase=kwargs["phase"],
            content_md=kwargs["content_md"],
            card_ids=kwargs["card_ids"],
            message_ids=kwargs["message_ids"],
            generated_at=dt.datetime(2026, 6, 7, 8, 0, tzinfo=dt.UTC),
        )

    monkeypatch.setattr(repo_mod, "upsert_digest", fake_upsert)

    llm = AsyncMock()
    llm.complete_json = AsyncMock(
        return_value={
            "content_md": "## Top priority\n- something",
            "card_ids": [str(real_card), str(hallucinated_card)],
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

    assert captured["card_ids"] == [real_card]
    assert captured["message_ids"] == [real_msg]
