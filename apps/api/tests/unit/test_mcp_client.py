from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from evercurrent.agent_tools.client import InProcessToolClient, UnknownToolError
from evercurrent.agent_tools.tools.get_thread_context import (
    get_thread_context as fn_get_thread_context,
)
from evercurrent.agent_tools.tools.get_user_context import (
    get_user_context as fn_get_user_context,
)
from evercurrent.agent_tools.tools.query_cards import query_cards as fn_query_cards
from evercurrent.agent_tools.tools.search_documents import (
    search_documents as fn_search_documents,
)
from evercurrent.agent_tools.tools.search_messages import (
    search_messages as fn_search_messages,
)


def test_default_dispatch_lists_all_phase4_tools() -> None:
    client = InProcessToolClient()
    expected = {
        "search_messages",
        "search_documents",
        "query_cards",
        "get_thread_context",
        "get_user_context",
    }
    assert set(client.tool_names) == expected


@pytest.mark.asyncio
async def test_call_dispatches_to_registered_tool() -> None:
    captured: dict[str, Any] = {}

    async def fake_tool(session: Any, *, query: str, project_id: uuid.UUID) -> str:
        captured["session"] = session
        captured["query"] = query
        captured["project_id"] = project_id
        return "ok"

    client = InProcessToolClient(dispatch={"search_messages": fake_tool})
    session = AsyncMock()
    project_id = uuid.uuid4()

    result = await client.call(
        "search_messages",
        session,
        {"query": "thermal", "project_id": project_id},
    )

    assert result == "ok"
    assert captured["session"] is session
    assert captured["query"] == "thermal"
    assert captured["project_id"] == project_id


@pytest.mark.asyncio
async def test_call_with_no_args_passes_empty_kwargs() -> None:
    called = False

    async def fake_tool(session: Any) -> str:  # noqa: ARG001
        nonlocal called
        called = True
        return "fine"

    client = InProcessToolClient(dispatch={"ping": fake_tool})
    result = await client.call("ping", AsyncMock())
    assert called
    assert result == "fine"


@pytest.mark.asyncio
async def test_call_unknown_tool_raises() -> None:
    client = InProcessToolClient(dispatch={})
    with pytest.raises(UnknownToolError):
        await client.call("nope", AsyncMock(), {})


def test_call_routes_each_default_tool_by_name() -> None:
    client = InProcessToolClient()
    expected = {
        "search_messages": fn_search_messages,
        "search_documents": fn_search_documents,
        "query_cards": fn_query_cards,
        "get_thread_context": fn_get_thread_context,
        "get_user_context": fn_get_user_context,
    }
    for name in expected:
        assert name in client.tool_names
