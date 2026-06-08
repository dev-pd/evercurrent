"""MCP (Model Context Protocol) tool layer.

Exposes read-only, typed tools that agents (Router in Phase 5, Digest in
Phase 8) consume. Tools are plain async functions registered into a
FastMCP server in `server.py`. An in-process client wrapper in
`client.py` lets internal callers dispatch tools without going over the
wire.

Conventions:
- Tools take an `AsyncSession` parameter — they never open their own.
- The session must have RLS context pre-set by the caller. Tools do not
  filter by `org_id` themselves; Postgres RLS does.
- Tools never raise on empty results — they return `[]` or `None`.
- Responses are Pydantic v2 strict, frozen models defined in `schemas.py`.
"""

from __future__ import annotations
