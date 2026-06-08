# Phase 4 — MCP tool layer

## Goal

Stand up an internal MCP (Model Context Protocol) server using FastMCP.
Expose the first set of read-only tools that future agents will call:
`search_messages`, `search_documents`, `query_cards`,
`get_thread_context`, `get_user_context`. Tools execute in-process via
a thin client wrapper so the Router and Digest agents call them through
the MCP protocol even when there's no separate process. No agent calls
these yet — that's Phase 5. This phase is the tool layer being built
on its own so it can be exercised, tested, and swapped to an
out-of-process server later with one config change.

## Why this phase, this order

We are about to write two LLM-driven agents (Router in Phase 5, Digest
in Phase 8). Both need a stable, typed, audited way to read data:
"give me the parent + replies of this message", "find documents that
look like this query", "what does this user own". If we bake those
lookups directly into the agents we get three problems: (a) the agents
end up with raw DB sessions and can read anything, breaking
multi-tenancy guarantees; (b) each agent ships its own ad-hoc helpers
and we can't swap one out; (c) we lose the property that the same tool
contract works for an external MCP client (Claude Desktop, a future
chat agent, a teammate's Cursor).

Doing this *before* Phase 5 forces the agent author to consume a
contract instead of inventing one. It also separates "I need a tool"
from "I'm an agent" cleanly — the tool is a function with a Pydantic
response schema, nothing more.

Order inside the phase: scaffold server → write schemas → write tools
one at a time with their tests → wire in-process client → prove RLS
still binds.

## Pre-requisites

- Phase 1 (infra: pytest harness, testcontainers Postgres)
- Phase 2 (auth + RLS: every query is filtered by `org_id` via a
  Postgres session setting)
- Phase 3 (Slack ingest: there are `messages`, `raw_events`, and
  `connector_channels` rows to query against)

## Files touched

### New

- `apps/api/src/evercurrent/mcp/__init__.py`
- `apps/api/src/evercurrent/mcp/server.py` — FastMCP server factory
- `apps/api/src/evercurrent/mcp/client.py` — in-process tool client
- `apps/api/src/evercurrent/mcp/schemas.py` — Pydantic response types
- `apps/api/src/evercurrent/mcp/tools/__init__.py`
- `apps/api/src/evercurrent/mcp/tools/search_messages.py`
- `apps/api/src/evercurrent/mcp/tools/search_documents.py`
- `apps/api/src/evercurrent/mcp/tools/query_cards.py`
- `apps/api/src/evercurrent/mcp/tools/get_thread_context.py`
- `apps/api/src/evercurrent/mcp/tools/get_user_context.py`
- `apps/api/tests/integration/mcp/test_search_messages.py`
- `apps/api/tests/integration/mcp/test_search_documents.py`
- `apps/api/tests/integration/mcp/test_query_cards.py`
- `apps/api/tests/integration/mcp/test_get_thread_context.py`
- `apps/api/tests/integration/mcp/test_get_user_context.py`
- `apps/api/tests/integration/mcp/test_rls.py` — cross-org leakage guard
- `docs/MCP.md` — short doc: what tools exist, response shape, how to
  add a new one

### Modified

- `apps/api/pyproject.toml` — add `fastmcp` (locked version), bump
  Pydantic if needed
- `apps/api/src/evercurrent/main.py` — mount the MCP server's ASGI
  endpoint at `/mcp` (off by default behind a flag for local dev)
- `apps/api/src/evercurrent/db/repositories/__init__.py` — expose the
  read-only repository methods the tools call (no new SQL in the tool
  files themselves)

### Deleted

- nothing

## Tasks

1. **Pin `fastmcp` in `pyproject.toml`.** Add to the main dep group,
   not dev. Run `uv lock && uv sync`. Note the exact version in
   `docs/DECISIONS.md` (locked because the protocol is still moving).
2. **Scaffold `mcp/server.py`.** Build a `FastMCP` app instance. Wire
   a startup hook that reads the current DB session factory from the
   DI container. Mount on the FastAPI app at `/mcp` so an external
   client *could* connect later — but only enable the route when
   `EVERCURRENT_MCP_EXPOSE=true` is set. Production default: off.
3. **Write `mcp/schemas.py`.** Pydantic v2 strict models:
   - `MessageRef { id: UUID, channel: str, author: str, text: str,
     posted_at: datetime, score: float | None }`
   - `ChunkRef { document_id: UUID, ordinal: int, section: str | None,
     text: str, similarity: float }`
   - `CardRef { id: UUID, kind: str, summary: str, status: str,
     decided_at: datetime | None }`
   - `ThreadContext { root: MessageRef, replies: list[MessageRef] }`
   - `UserContext { membership_id: UUID, display_name: str, role: str,
     owned_subsystems: list[str], topic_weights: dict[str, float] }`
   - All with `model_config = ConfigDict(strict=True, frozen=True)`.
4. **Implement tools, one file per tool.** Each file exports a single
   `async def` decorated with `@mcp.tool()`. Tool body delegates to a
   repository method — no inline SQL.
   - `search_messages(query: str, project_id: UUID, limit: int = 10)`
     — full-text `tsvector` match on `messages.text` joined with
     `message_tags` (topic filter optional). Sort by recency. No LLM.
   - `search_documents(query: str, project_id: UUID, k: int = 5)` —
     embed `query` via the Voyage adapter, ANN over
     `document_chunks.embedding` with cosine distance. Returns chunks
     scoped to the project's documents.
   - `query_cards(project_id: UUID, kind: str | None = None,
     status: str | None = None)` — pure SQL filter on `cards`.
   - `get_thread_context(message_id: UUID)` — load the message, walk
     to `thread_root_id`, fetch siblings.
   - `get_user_context(membership_id: UUID)` — join
     `org_memberships` + `project_members`, return role,
     `owned_subsystems`, `topic_weights`.
5. **Tool argument validation.** Every tool that takes a `project_id`
   raises a typed error if it's missing or doesn't belong to the
   current org. Don't rely on the LLM to never forget. The MCP
   protocol surfaces this as a tool error the agent can recover from.
6. **In-process client (`mcp/client.py`).** Thin wrapper class
   `InProcessMCPClient`. Exposes `async call(tool_name: str, args:
   dict) -> dict`. Internally dispatches to the FastMCP tool registry
   *without* going over JSON-RPC — same call shape, no network. This
   is what Router and Digest will use.
7. **Wire the DB session for each tool call.** Tools run inside an
   `async with session_factory() as session:` block opened by the
   client wrapper. Before the body runs, the client sets
   `app.current_org_id` on that session (Phase 2's RLS helper). This
   means tools cannot leak across tenants even if a bug skips a
   `WHERE org_id =`.
8. **Tests, written first** (TDD). For each tool:
   - happy path: seed a project, call tool, assert expected refs come
     back, assert response is a Pydantic instance (not a dict).
   - empty case: empty query, empty project — returns `[]`, doesn't
     crash.
   - missing-arg case: omit `project_id` → raises validation error
     with the tool name in the message.
   - cross-org case (`test_rls.py`): seed two orgs, call the tool
     while the session is bound to org A, assert org B's rows never
     appear in the response.
9. **Log every tool call.** structlog event `mcp.tool_call` with
   `tool_name`, `args_redacted`, `org_id`, `duration_ms`, `result_count`.
   No PII in args by default; redact `query` strings to length only
   unless `EVERCURRENT_MCP_LOG_QUERIES=true`.
10. **`docs/MCP.md`.** One page: list of tools, response schema,
    how to add a new one (4 steps: add schema, add repo method, add
    tool file, add tests).
11. **Lint + test.** `make lint && make test-integration` green.
12. **Commit.** `feat(phase-4): MCP tool layer with FastMCP and five
    read-only tools`.

## Test plan

TDD. Each tool gets its own integration test file under
`tests/integration/mcp/`. Tests run against a real testcontainers
Postgres, with the per-test transaction fixture from Phase 1.

Order tests are written:

1. `test_get_user_context.py` — simplest, no joins beyond
   `org_memberships`.
2. `test_query_cards.py` — pure SQL filter, exercises status + kind
   combinations.
3. `test_get_thread_context.py` — self-referential FK walk.
4. `test_search_messages.py` — tsvector search, hits the postgres
   full-text index. Asserts ordering by recency.
5. `test_search_documents.py` — uses a stubbed embedder (returns a
   fixed vector for "thermal margin") so the test doesn't hit Voyage
   in CI.
6. `test_rls.py` — the load-bearing one. Seeds org A + org B with
   overlapping data, exercises every tool, asserts org B rows are
   never returned to an org-A-bound session.

Each test follows: arrange (seed via factories) → act (call the tool
via `InProcessMCPClient`) → assert (Pydantic instance, expected
fields, no extra rows).

## Definition of done

- [ ] FastMCP server boots and registers all five tools
- [ ] Each tool has a Pydantic response schema in `mcp/schemas.py`,
      strict mode, frozen
- [ ] `InProcessMCPClient` calls every tool successfully
- [ ] Every tool has a passing integration test
- [ ] `test_rls.py` proves cross-org isolation for every tool
- [ ] Tools reject missing or wrong-org `project_id` with a typed
      error
- [ ] structlog emits `mcp.tool_call` for every call with timing
- [ ] `docs/MCP.md` documents the surface and the "add a tool" recipe
- [ ] `make lint` and `make test-integration` green
- [ ] One commit on `feat/phase-4-mcp` branch, merged to `main`

## Common pitfalls

- **Letting the tool open its own DB session.** Every tool must take
  the session from the client wrapper. If a tool reaches for the
  session factory directly, RLS won't be set and the test_rls case
  will fail — or worse, pass in dev but leak in prod.
- **Returning raw dicts from tools.** The FastMCP `@tool` decorator
  will serialise anything. If you return a dict the agent sees a
  loose shape and the schema drift bites later. Always return the
  Pydantic model; let FastMCP serialise it.
- **Forgetting the cosine distance direction.** pgvector's
  `<=> ` is distance, not similarity. Sort ascending. Convert to
  similarity = `1 - distance` only in the response, not in the
  ORDER BY.
- **Embedding the query inside the tool with no cache.** Even at
  dev scale, repeated identical queries (test runs) burn Voyage
  credits. Cache by `hash(query)` in Redis with a short TTL. Skip
  the cache when `EVERCURRENT_MCP_BUST_CACHE=true` for tests that
  need a hit count.
- **Exposing `/mcp` publicly by default.** That hands raw tool
  access to anyone with the URL. Default off, env-flagged on.
  External exposure is a Phase 12+ concern.
- **Tests that depend on tsvector + Voyage being available.** Stub
  the embedder in CI; rely on the Postgres testcontainer for
  `to_tsvector`. Don't gate CI on a paid API.

## Recap — what you'll be able to explain after this phase

- "Why MCP and not a bespoke tool registry?"
  → MCP is the emerging protocol for tool-using agents (Anthropic
    shipped it; Claude Desktop speaks it). Writing to a protocol
    instead of a private interface means our tools work with any
    MCP client. Same tools could power Claude Desktop or a teammate's
    Cursor session. We pay no extra cost over a private registry
    today and get portability for free.
- "Why are these tools read-only?"
  → Agents reason; workflows mutate. Side-effecting changes
    (creating a Card, writing `message_tags`, sending a DM) happen
    in deterministic Celery tasks that *follow* the agent's
    decision. Keeping tools read-only means we can replay an
    agent's tool calls during eval without worrying about state
    drift, and the agent can't accidentally double-write a row.
- "Why Pydantic strict on responses?"
  → The agent sees the JSON. If we let `Optional[str]` silently
    become `None` because of a join miss, the agent confabulates
    around it. Strict mode + frozen forces us to acknowledge every
    field's nullability up front, and the schemas become the
    contract between tools and agents.
- "Why in-process for take-home, but MCP protocol-shaped?"
  → Running a separate MCP server process inside docker-compose is
    overhead nobody benefits from at this scale. The protocol
    shape gives us optionality: when we eventually want to scale
    out, or expose tools to external clients, swapping the
    `InProcessMCPClient` for a stdio or HTTP client is a one-line
    change. No agent code touches it.
- "How do you guarantee RLS holds even when the agent calls
  directly?"
  → The client wrapper sets `app.current_org_id` on the DB session
    *before* the tool body runs. Every query the tool issues goes
    through that session. Postgres applies RLS policies. The
    cross-org test proves it.

## Talking points (for the grill)

1. **"MCP, not bespoke."** Protocol-shaped from day one. Portable to
   Claude Desktop, external chat clients, future agents we haven't
   built. Cheap option, large upside.
2. **"Tools are typed."** Pydantic strict response schemas. Agents
   reason about a known shape, not a loose dict.
3. **"Read-only by design."** Agents propose; deterministic tasks
   dispose. Makes replay safe, makes the audit story clean.
4. **"RLS-bound at the session."** Even if an agent forgot to filter
   by `org_id`, Postgres would. Defence in depth.
5. **"Five tools is enough for Router + Digest."** No speculative
   tools. Each one earned its spot by being needed in Phase 5 or 8.
6. **"In-process today, server tomorrow."** Same protocol. One config
   change to swap.
