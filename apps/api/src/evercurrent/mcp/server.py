"""FastMCP server wiring.

This module is intentionally minimal for Phase 4. The build doc says
agents won't consume tools over the wire yet (Phase 5+), so we keep the
registration here as plain async functions and a `build_server()` shim
that *will* attach them to a `FastMCP` instance once `fastmcp` is added
to dependencies.

Registration approach (TODO when `fastmcp` is installed):

    from fastmcp import FastMCP
    server = FastMCP("evercurrent")
    server.tool()(search_messages)
    server.tool()(search_documents)
    server.tool()(query_cards)
    server.tool()(get_thread_context)
    server.tool()(get_user_context)
    return server

Until then, `build_server()` returns a sentinel `_FastMCPPlaceholder` so
imports at module load don't require the dep. The InProcessMCPClient in
`client.py` already gives Router + Digest a working dispatch path that
matches the MCP call shape, so this placeholder doesn't block Phase 5.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from evercurrent.mcp.tools import (
    get_thread_context,
    get_user_context,
    query_cards,
    search_documents,
    search_messages,
)

log = structlog.get_logger(__name__)


TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "search_messages": search_messages,
    "search_documents": search_documents,
    "query_cards": query_cards,
    "get_thread_context": get_thread_context,
    "get_user_context": get_user_context,
}


class _FastMCPPlaceholder:
    """Stand-in for `fastmcp.FastMCP` until the dependency is added.

    Exposes `tools` so callers can introspect what's registered. Replace
    with a real `FastMCP("evercurrent")` instance per the docstring at
    the top of this module.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, Callable[..., Any]] = dict(TOOL_REGISTRY)

    def list_tools(self) -> list[str]:
        return sorted(self.tools)


def build_server(name: str = "evercurrent") -> _FastMCPPlaceholder:
    """Construct the MCP server and register every tool.

    Returns a placeholder today; will return a real `FastMCP` instance
    once `fastmcp` is pinned in `pyproject.toml`. The tool functions
    themselves do not change.
    """
    server = _FastMCPPlaceholder(name)
    log.info("mcp.server_built", name=name, tool_count=len(server.tools))
    return server
