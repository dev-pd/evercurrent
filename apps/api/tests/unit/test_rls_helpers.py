from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from evercurrent.tenancy.rls import clear_org_context, set_org_context


@pytest.mark.asyncio
async def test_set_org_context_calls_db_function() -> None:
    session = AsyncMock()
    org_id = uuid.uuid4()

    await set_org_context(session, org_id)

    session.execute.assert_called_once()
    call_args = session.execute.call_args
    assert "SELECT set_org_context(:id)" in str(call_args[0][0])
    assert call_args[0][1] == {"id": str(org_id)}


@pytest.mark.asyncio
async def test_clear_org_context_calls_db_function() -> None:
    session = AsyncMock()

    await clear_org_context(session)

    session.execute.assert_called_once()
    assert "SELECT clear_org_context()" in str(session.execute.call_args[0][0])
