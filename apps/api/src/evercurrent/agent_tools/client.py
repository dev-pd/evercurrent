from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.agent_tools.tools import (
    get_thread_context,
    get_user_context,
    query_cards,
    search_documents,
    search_messages,
)

log = structlog.get_logger(__name__)


class UnknownToolError(ValueError):
    pass


ToolFn = Callable[..., Awaitable[Any]]


def _build_dispatch() -> dict[str, ToolFn]:
    return {
        "search_messages": search_messages,
        "search_documents": search_documents,
        "query_cards": query_cards,
        "get_thread_context": get_thread_context,
        "get_user_context": get_user_context,
    }


class InProcessToolClient:
    def __init__(self, dispatch: dict[str, ToolFn] | None = None) -> None:
        self._dispatch: dict[str, ToolFn] = dispatch or _build_dispatch()

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._dispatch)

    async def call(
        self,
        tool_name: str,
        session: AsyncSession,
        args: dict[str, Any] | None = None,
    ) -> Any:
        fn = self._dispatch.get(tool_name)
        if fn is None:
            log.warning("mcp.unknown_tool", tool_name=tool_name)
            raise UnknownToolError(tool_name)
        kwargs = args or {}
        return await fn(session, **kwargs)
