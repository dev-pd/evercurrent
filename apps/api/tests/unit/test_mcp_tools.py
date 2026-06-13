from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from evercurrent.mcp.schemas import (
    CardRef,
    ChunkRef,
    MessageRef,
    ThreadContext,
    UserContext,
)
from evercurrent.mcp.tools.get_thread_context import get_thread_context
from evercurrent.mcp.tools.get_user_context import get_user_context
from evercurrent.mcp.tools.query_cards import query_cards
from evercurrent.mcp.tools.search_documents import search_documents
from evercurrent.mcp.tools.search_messages import search_messages


def _mappings_result(rows: list[dict[str, Any]]) -> MagicMock:
    result = MagicMock()
    mappings = MagicMock()
    mappings.__iter__ = lambda _self: iter(rows)
    mappings.first = MagicMock(return_value=rows[0] if rows else None)
    result.mappings = MagicMock(return_value=mappings)
    return result


@pytest.fixture
def now_utc() -> dt.datetime:
    return dt.datetime(2026, 6, 7, 12, 0, tzinfo=dt.UTC)


@pytest.mark.asyncio
async def test_search_messages_empty_query_returns_empty() -> None:
    session = AsyncMock()
    out = await search_messages(
        session,
        query="   ",
        project_id=uuid.uuid4(),
        limit=5,
    )
    assert out == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_search_messages_returns_message_refs(now_utc: dt.datetime) -> None:
    project_id = uuid.uuid4()
    row_id = uuid.uuid4()
    rows = [
        {
            "id": row_id,
            "channel": "mech-design",
            "author": "Lin",
            "text": "thermal margin tight on ECO-178",
            "posted_at": now_utc,
        },
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result(rows))

    out = await search_messages(
        session,
        query="thermal",
        project_id=project_id,
        limit=5,
    )

    assert len(out) == 1
    assert isinstance(out[0], MessageRef)
    assert out[0].id == row_id
    assert out[0].channel == "mech-design"
    assert out[0].author == "Lin"

    session.execute.assert_awaited_once()
    call = session.execute.await_args
    assert call is not None
    sql_text = str(call.args[0])
    params = call.args[1]
    assert "FROM messages" in sql_text
    assert "ILIKE" in sql_text
    assert "%thermal%" in params["patterns"]
    assert params["limit"] == 5


@pytest.mark.asyncio
async def test_search_messages_no_results_returns_empty() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    out = await search_messages(
        session,
        query="nothing-matches",
        project_id=uuid.uuid4(),
    )
    assert out == []


class _StubEmbedder:
    def __init__(self, dim: int = 512) -> None:
        self._vec = [0.0] * dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(self._vec) for _ in texts]

    async def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        return list(self._vec)


@pytest.mark.asyncio
async def test_search_documents_empty_query_returns_empty() -> None:
    session = AsyncMock()
    out = await search_documents(
        session,
        query="",
        project_id=uuid.uuid4(),
        embedder=_StubEmbedder(),
    )
    assert out == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_search_documents_returns_chunk_refs() -> None:
    project_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    rows = [
        {
            "document_id": doc_id,
            "ordinal": 3,
            "section": "Thermal",
            "text": "AlumWest alloy raised the margin by 12C",
            "similarity": 0.87,
        },
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result(rows))

    out = await search_documents(
        session,
        query="thermal margin",
        project_id=project_id,
        limit=3,
        embedder=_StubEmbedder(),
    )

    assert len(out) == 1
    assert isinstance(out[0], ChunkRef)
    assert out[0].document_id == doc_id
    assert out[0].ordinal == 3
    assert out[0].section == "Thermal"
    assert out[0].similarity == pytest.approx(0.87)

    call = session.execute.await_args
    assert call is not None
    sql_text = str(call.args[0])
    params = call.args[1]
    assert "FROM document_chunks" in sql_text
    assert "JOIN documents" in sql_text
    assert params["project_id"] == project_id
    assert params["limit"] == 3
    assert params["qvec"].startswith("[")
    assert params["qvec"].endswith("]")


@pytest.mark.asyncio
async def test_query_cards_filters_status(now_utc: dt.datetime) -> None:
    project_id = uuid.uuid4()
    card_id = uuid.uuid4()
    rows = [
        {
            "id": card_id,
            "kind": "decision",
            "summary": "Switch to AlumWest",
            "status": "open",
            "affected_subsystems": ["materials"],
            "decided_at": now_utc,
        },
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result(rows))

    out = await query_cards(
        session,
        project_id=project_id,
        status="open",
    )

    assert len(out) == 1
    assert isinstance(out[0], CardRef)
    assert out[0].id == card_id
    assert out[0].status == "open"
    assert out[0].affected_subsystems == ["materials"]

    call = session.execute.await_args
    assert call is not None
    sql_text = str(call.args[0])
    params = call.args[1]
    assert "FROM cards" in sql_text
    assert params["status"] == "open"
    assert params["kind"] is None


@pytest.mark.asyncio
async def test_query_cards_no_results_returns_empty() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    out = await query_cards(session, project_id=uuid.uuid4(), kind="risk")
    assert out == []


@pytest.mark.asyncio
async def test_get_thread_context_unknown_message_returns_none() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    out = await get_thread_context(session, message_id=uuid.uuid4())
    assert out is None


@pytest.mark.asyncio
async def test_get_thread_context_root_with_replies(now_utc: dt.datetime) -> None:
    root_id = uuid.uuid4()
    reply_id = uuid.uuid4()
    root_row = {
        "id": root_id,
        "thread_root_id": None,
        "channel": "supply-chain",
        "author": "Mei",
        "text": "ExtruCo strike confirmed",
        "posted_at": now_utc,
    }
    reply_row = {
        "id": reply_id,
        "channel": "supply-chain",
        "author": "Lin",
        "text": "happy to sign off",
        "posted_at": now_utc + dt.timedelta(minutes=5),
    }
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _mappings_result([root_row]),
            _mappings_result([reply_row]),
        ],
    )

    out = await get_thread_context(session, message_id=root_id)

    assert isinstance(out, ThreadContext)
    assert out.root.id == root_id
    assert out.root.author == "Mei"
    assert len(out.replies) == 1
    assert out.replies[0].id == reply_id
    assert out.replies[0].author == "Lin"


@pytest.mark.asyncio
async def test_get_thread_context_walks_up_from_reply(now_utc: dt.datetime) -> None:
    root_id = uuid.uuid4()
    reply_id = uuid.uuid4()
    reply_row = {
        "id": reply_id,
        "thread_root_id": root_id,
        "channel": "supply-chain",
        "author": "Lin",
        "text": "happy to sign off",
        "posted_at": now_utc + dt.timedelta(minutes=5),
    }
    root_row = {
        "id": root_id,
        "thread_root_id": None,
        "channel": "supply-chain",
        "author": "Mei",
        "text": "ExtruCo strike confirmed",
        "posted_at": now_utc,
    }
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _mappings_result([reply_row]),
            _mappings_result([root_row]),
            _mappings_result([]),
        ],
    )

    out = await get_thread_context(session, message_id=reply_id)

    assert isinstance(out, ThreadContext)
    assert out.root.id == root_id
    assert out.replies == []
    assert session.execute.await_count == 3


@pytest.mark.asyncio
async def test_get_user_context_unknown_returns_none() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    out = await get_user_context(session, membership_id=uuid.uuid4())
    assert out is None


@pytest.mark.asyncio
async def test_get_user_context_returns_strict_model() -> None:
    membership_id = uuid.uuid4()
    row = {
        "membership_id": membership_id,
        "display_name": "Lin",
        "role": "member",
        "slack_user_id": "ULIN",
        "email": "lin@example.com",
        "owned_subsystems": ["thermal", "powertrain"],
        "topic_weights": {"thermal": 0.9, "supply_chain": 0.4},
    }
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([row]))

    out = await get_user_context(session, membership_id=membership_id)

    assert isinstance(out, UserContext)
    assert out.membership_id == membership_id
    assert out.role == "member"
    assert out.owned_subsystems == ["thermal", "powertrain"]
    assert out.topic_weights == {"thermal": 0.9, "supply_chain": 0.4}


@pytest.mark.asyncio
async def test_get_user_context_handles_missing_user_row() -> None:
    membership_id = uuid.uuid4()
    row = {
        "membership_id": membership_id,
        "display_name": "Mei",
        "role": "admin",
        "slack_user_id": None,
        "email": "mei@example.com",
        "owned_subsystems": None,
        "topic_weights": None,
    }
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([row]))

    out = await get_user_context(session, membership_id=membership_id)

    assert isinstance(out, UserContext)
    assert out.owned_subsystems == []
    assert out.topic_weights == {}


def test_message_ref_is_frozen(now_utc: dt.datetime) -> None:
    ref = MessageRef(
        id=uuid.uuid4(),
        channel="x",
        author="y",
        text="z",
        posted_at=now_utc,
    )
    with pytest.raises(ValidationError):
        ref.channel = "other"  # type: ignore[misc]
