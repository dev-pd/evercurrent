"""In-process MCP client.

Router (Phase 5) and Digest (Phase 8) agents call MCP tools through this
wrapper. It maintains an `async` dispatch table mapping tool name →
tool function. Same call-shape as a wire-level MCP client (`call(name,
args)`), no JSON-RPC round-trip. Swapping for an out-of-process MCP
client later is a single-line change in the agent's constructor.

The caller supplies the AsyncSession (already RLS-bound) on every call.
The client never opens its own session — that's a deliberate constraint
so tenancy guarantees stay verifiable at the route boundary.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.mcp.tools import (
    get_thread_context,
    get_user_context,
    query_cards,
    search_documents,
    search_messages,
)

log = structlog.get_logger(__name__)


class UnknownToolError(ValueError):
    """Raised when `call()` receives a tool name that isn't registered."""


ToolFn = Callable[..., Awaitable[Any]]


def _build_dispatch() -> dict[str, ToolFn]:
    return {
        "search_messages": search_messages,
        "search_documents": search_documents,
        "query_cards": query_cards,
        "get_thread_context": get_thread_context,
        "get_user_context": get_user_context,
    }


class InProcessMCPClient:
    """Dispatch table over the registered MCP tool functions."""

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
        """Dispatch to the named tool with `args` as kwargs.

        The session must already have RLS context bound by the caller.
        """
        fn = self._dispatch.get(tool_name)
        if fn is None:
            log.warning("mcp.unknown_tool", tool_name=tool_name)
            raise UnknownToolError(tool_name)
        kwargs = args or {}
        return await fn(session, **kwargs)
