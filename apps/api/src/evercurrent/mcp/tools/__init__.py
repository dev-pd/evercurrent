"""MCP tools — one async function per tool, one file per tool.

Each tool takes an `AsyncSession` (already RLS-bound by the caller) and
returns a Pydantic strict model from `evercurrent.mcp.schemas`. Tools
never raise on empty results — they return `[]` or `None`.
"""

from __future__ import annotations

from evercurrent.mcp.tools.get_thread_context import get_thread_context
from evercurrent.mcp.tools.get_user_context import get_user_context
from evercurrent.mcp.tools.query_cards import query_cards
from evercurrent.mcp.tools.search_documents import search_documents
from evercurrent.mcp.tools.search_messages import search_messages

__all__ = [
    "get_thread_context",
    "get_user_context",
    "query_cards",
    "search_documents",
    "search_messages",
]
