# Phase 5 — Router agent

## Goal

Build the **per-message classifier**: an agent that reads an inbound
`raw_event`, normalises it into a `messages` row, decides what kind of
message it is (decision candidate, status update, question, noise),
tags it (topic, urgency, entities, affected roles), and decides
whether it should become a Knowledge Card. Uses Haiku 4.5 via the LLM
client. Calls MCP tools (`get_thread_context`, `get_user_context`)
from Phase 4 when context is needed. Output is parsed into the
`RouterDecision` Pydantic schema, persisted as a `message_tags` row,
and — if `should_create_card` — enqueues `build_card` (which Phase 6
implements).

## Why this phase, this order

The Router agent is the first place the LLM actually decides
something autonomously in this codebase. Everything before this phase
moves bytes around; this phase introduces intelligence on the
critical path of every Slack message.

It comes after Phase 4 (MCP tools) because the agent needs a typed
toolbox to call. It comes before Phase 6 (Cards) because Cards are
*downstream of* the Router's decision — there's no point building the
Card pipeline until we know what produces the signal to build one.
And it comes before Phase 7 (Scoring) because scoring reads
`message_tags.topic`, `urgency`, and `affected_roles`, which the
Router writes.

Order inside the phase: schema → prompt → agent loop → Celery task →
deterministic tests with a mocked LLM → eval against hand-labelled
fixtures.

## Pre-requisites

- Phase 2 (auth + RLS, so `messages.org_id` is set correctly)
- Phase 3 (Slack ingest writes `raw_events` and triggers the
  `route_message` task with a `raw_event_id`)
- Phase 4 (MCP tools: `get_thread_context`, `get_user_context`,
  `InProcessMCPClient`)
- `llm/client.py` from earlier infra (the Anthropic wrapper, the
  only place the SDK is imported)
- `llm/tiering.py` exposes `haiku()` returning the configured Haiku
  4.5 model id

## Files touched

### New

- `apps/api/src/evercurrent/routing/__init__.py`
- `apps/api/src/evercurrent/routing/router_agent.py` — the agent loop
- `apps/api/src/evercurrent/routing/schemas.py` — `RouterDecision`
- `apps/api/src/evercurrent/routing/normaliser.py` — `raw_event` →
  `messages` row
- `apps/api/src/evercurrent/routing/prompts/router_system.txt`
- `apps/api/src/evercurrent/routing/prompts/router_user.txt.j2`
- `apps/api/src/evercurrent/routing/repository.py` — `message_tags`
  write helpers
- `apps/api/tests/integration/routing/test_router_agent.py`
- `apps/api/tests/integration/routing/test_route_message_task.py`
- `apps/api/tests/integration/routing/test_normaliser.py`
- `apps/api/tests/evals/router/fixtures.jsonl` — 50 hand-labelled
  messages
- `apps/api/tests/evals/router/test_accuracy.py` — labelled-accuracy
  eval

### Modified

- `apps/api/src/evercurrent/jobs/celery_tasks.py` — add
  `route_message(raw_event_id: UUID)`
- `apps/api/src/evercurrent/api/routers/events.py` — publish
  `events:<org_id>` SSE event `{type: "message_tagged", payload: ...}`
  (helper invoked from the Celery task, not the route)
- `apps/api/src/evercurrent/db/models.py` — confirm `message_tags`
  matches the schema (already declared in Phase 3); no DDL
- `apps/api/pyproject.toml` — add `tenacity` if not already pinned;
  add `jinja2` for prompt templating

### Deleted

- nothing

## Tasks

1. **`RouterDecision` schema** (`routing/schemas.py`):
   ```python
   class RouterDecision(BaseModel):
       model_config = ConfigDict(strict=True, frozen=True)
       topic: str | None
       urgency: Literal["low", "normal", "high", "critical"]
       entities: list[str]
       affected_roles: list[str]
       should_create_card: bool
       card_kind: Literal["decision", "risk", "question"] | None
       card_summary: str | None
       confidence: float = Field(ge=0.0, le=1.0)
   ```
   Validator: `card_kind` and `card_summary` are non-None iff
   `should_create_card` is True. Reject otherwise.
2. **`router_system.txt`** — system prompt. Includes: role list for
   the project, definition of each `card_kind`, urgency rubric,
   instruction to call `get_thread_context` only when the message
   text alone is ambiguous, instruction to return the final answer
   as JSON matching the schema. Keep under 800 tokens.
3. **`router_user.txt.j2`** — Jinja template. Renders the message
   text, author display name, channel, timestamp, and a short
   thread snippet if the message has a `thread_root_id`.
4. **`normaliser.py`.** `parse_slack_event(raw: dict) -> MessageRow`.
   Maps Slack's `event.message` shape into the `messages` columns:
   `source="slack"`, `external_id=event.ts`, `channel`, `text`,
   `author_display_name`, `posted_at`, `thread_root_id` (looked up
   by `thread_ts` if present). Pure function, unit-testable.
5. **`router_agent.py`.** Class `RouterAgent` with:
   ```python
   async def classify(self, message: MessageRow,
                       membership: OrgMembership,
                       project: Project) -> RouterDecision
   ```
   Internals:
   1. Render `router_system.txt` with project context (role list,
      phase concerns).
   2. Render `router_user.txt.j2` with the message + thread snippet.
   3. Call `llm.haiku.create_with_tools(system, user, tools=[...])`
      where `tools` are the FastMCP tool definitions for
      `get_thread_context` and `get_user_context`, exported from
      `mcp/server.py` as a list of `tool_use_param` dicts.
   4. Loop: read response → if `stop_reason == "tool_use"`, dispatch
      via `InProcessMCPClient.call`, append `tool_result` to messages,
      call Haiku again. Cap iterations at 4.
   5. Final assistant message text → JSON parse → `RouterDecision`.
   6. Pydantic validation. On `ValidationError`, retry once with an
      appended user message: `"Your last response did not match the
      schema. Re-emit with these fields: {...}"`. Second failure →
      log + return a `"uncategorized"` fallback with `urgency=normal`,
      `should_create_card=False`.
6. **Celery task `route_message`** in `jobs/celery_tasks.py`:
   ```python
   @celery_app.task(name="route_message",
                    bind=True, max_retries=3,
                    autoretry_for=(TransientLLMError,),
                    retry_backoff=True)
   def route_message(self, raw_event_id: UUID) -> None: ...
   ```
   Task body:
   1. Load `raw_event` row.
   2. Set `app.current_org_id` on the session.
   3. `normaliser.parse_slack_event` → upsert `messages` row.
   4. Resolve `author_membership_id` from `slack_user_id`.
   5. `await router_agent.classify(...)`.
   6. Upsert `message_tags` row (UNIQUE on `message_id`). Always
      write, even on fallback — audit trail.
   7. If `decision.should_create_card`, enqueue `build_card.delay(
      message_id, kind, summary_hint)` (Phase 6 implements
      `build_card`; Phase 5 wires the enqueue with a stub task that
      just logs).
   8. Publish `events:<org_id>` SSE event:
      `{type: "message_tagged", payload: {message_id, topic,
       urgency, should_create_card}}`.
7. **Logging.** `audit_log` row per call (`actor="router_agent"`,
   payload with tokens + latency). structlog event
   `router.classify` with `message_id`, `org_id`, `decision`,
   `iter_count`, `latency_ms`.
8. **Cost + latency targets.**
   - p50 latency < 1.5s end-to-end (raw_event picked up → tags
     written).
   - p99 latency < 4s.
   - Per-message cost < $0.001 (Haiku 4.5 input ~1k tokens, output
     ~200 tokens at most).
   Emit a structlog warning if a call exceeds these.
9. **Deterministic tests** (`test_router_agent.py`). Mock the LLM
   client to return a canned tool-use sequence followed by a JSON
   `RouterDecision`. Cases:
   - happy path: decision_candidate, asserts `RouterDecision` parses
     and matches.
   - thread context branch: LLM calls `get_thread_context`, tool
     returns a stub; assert the second LLM call sees the tool
     result in its message list.
   - schema-drift branch: LLM returns invalid JSON; assert one
     retry happens; assert fallback on second failure.
   - validator branch: LLM returns `should_create_card=True` with
     `card_kind=None`; assert `ValidationError` → retry path.
10. **Task test** (`test_route_message_task.py`). Seed a
    `raw_events` row, mock the router agent to return a fixed
    `RouterDecision`, invoke `route_message` synchronously, assert:
    - `messages` row written
    - `message_tags` row written with the right fields
    - SSE event published (mock the Redis publisher, assert call)
    - `build_card` enqueued when `should_create_card=True`
    - `build_card` NOT enqueued when False
11. **Eval harness** (`tests/evals/router/`). 50 hand-labelled
    fixtures in `fixtures.jsonl`, each row:
    `{"text": "...", "channel": "...", "author_role": "...",
      "expected": {"urgency": "...", "should_create_card": ...,
                   "card_kind": "..."}}`.
    `test_accuracy.py` runs the real Router against each, computes
    accuracy on `urgency`, `should_create_card`, `card_kind`. Asserts
    > 90% on `should_create_card`, > 85% on `card_kind`. Runs under
    `make eval`, NOT in CI.
12. **Commit.** `feat(phase-5): router agent — Haiku classifier with
    MCP tool calls and Pydantic-validated decisions`.

## Test plan

Two layers.

**Deterministic layer** (runs in CI, mocked LLM):
- `test_normaliser.py` — pure function, table-driven cases for the
  Slack payload shapes (plain message, thread reply, edited, deleted,
  file_share).
- `test_router_agent.py` — agent loop with a `FakeLLMClient` that
  scripts the response sequence. Asserts schema parsing, retry, tool
  dispatch, fallback.
- `test_route_message_task.py` — Celery task end-to-end against
  testcontainers Postgres + a mocked Redis publisher.

**Eval layer** (`make eval`, not CI):
- `test_accuracy.py` — real Haiku calls against 50 fixtures. Asserts
  the accuracy thresholds. If it dips below threshold, prompt needs
  work — surfaced in `docs/EVAL_BASELINE.md`.

TDD order: schema test first, then normaliser, then agent loop, then
task, then eval last (because eval needs a working agent).

## Definition of done

- [ ] `RouterDecision` schema with strict validation + cross-field
      validator
- [ ] System + user prompts in `routing/prompts/`, not inline
- [ ] `RouterAgent.classify` loops over tool_use, parses output,
      retries once on schema drift, falls back on second failure
- [ ] Celery task `route_message` wired end-to-end:
      `raw_event` → `messages` + `message_tags` → SSE event →
      `build_card` enqueue
- [ ] `message_tags` row written on every call (even fallback)
- [ ] `audit_log` row per LLM call with token counts + latency
- [ ] Deterministic tests pass in CI
- [ ] Eval harness produces an accuracy number for the 50-fixture set
- [ ] p50 latency under 1.5s on a warm path
- [ ] One commit on `feat/phase-5-router` branch, merged to `main`

## Common pitfalls

- **Using Sonnet "just to be safe."** Tagging is easy classification.
  Haiku 4.5 is 5x cheaper and 3x faster, and the eval threshold is
  set assuming Haiku. If Haiku misses the threshold we tune the
  prompt before considering a model bump.
- **Letting the LLM hallucinate a tool call schema.** Don't write the
  tool descriptions by hand in the system prompt. Export them from
  `mcp/server.py` so prompt and protocol stay in sync.
- **No retry on `ValidationError`.** First-pass LLM JSON is often
  almost-right (missing comma, wrong enum casing). One targeted
  retry with the explicit schema reminder fixes ~80% of misses.
  Without it, every failure becomes a fallback row and the eval
  number tanks.
- **Forgetting to write `message_tags` on fallback.** If you skip the
  write you lose the audit trail of "the agent saw this message and
  failed." Always write; use `tagged_by_model="fallback"` so eval
  filters them out.
- **Enqueuing `build_card` synchronously inside the task.** Keep
  routing fast. `build_card` is its own Celery task; the router
  enqueues, doesn't await.
- **SSE event published before the DB write commits.** Browser
  refetches, hits a race, sees stale data. Publish *after* the
  commit, inside the same `try/finally` so a crash doesn't drop
  the event silently — log a missed publish.
- **Prompt drift unnoticed.** When the prompt changes, the eval
  baseline can move. Commit the prompt + the eval result number
  together so the diff is reviewable.

## Recap — what you'll be able to explain after this phase

- "Why Haiku, not Sonnet, for routing?"
  → Routing is per-message and runs on every inbound event. At a
    real org's volume (~5k messages/day), that's the cost-sensitive
    hot path. Haiku 4.5 hits the accuracy bar on classification +
    extraction with a 5x cost and 3x latency advantage. Sonnet is
    reserved for the writing tasks (Digest, Card body) where the
    quality difference shows up. The tiering decision is in
    `llm/tiering.py` so it's one line to flip if Haiku regresses.
- "Why does the agent loop, instead of one-shot prompting?"
  → Some messages need thread context to be classified correctly
    ("looks fine to me" is meaningless alone; in a thread about a
    bracket redesign it's a sign-off). One-shot prompts either
    always fetch thread context (wasteful, slow) or never do
    (wrong). The agent loop lets Haiku decide per-message whether
    it needs the extra fetch. Cap at 4 iterations to bound cost.
- "Why is the output Pydantic-validated instead of free text?"
  → Downstream code (scoring, card builder) reads structured
    fields. A free-text response would mean parsing prose forever.
    Pydantic strict mode catches drift the moment the LLM forgets
    an enum value; we retry once with the schema reminder, then
    fall back rather than write garbage.
- "What happens when the LLM fails?"
  → Two layers. (1) Schema validation fails → retry once with an
    explicit re-emit instruction. (2) Still fails → write a
    fallback `message_tags` row with `topic=null`,
    `urgency="normal"`, `should_create_card=False`,
    `tagged_by_model="fallback"`. The message stays in the
    pipeline and downstream still scores it (low), so we never
    silently drop messages. The fallback row is the audit trail
    that the model saw it and choked.
- "How do you know the agent actually works?"
  → The 50-fixture eval. Hand-labelled. Accuracy thresholds in
    `test_accuracy.py`. Baseline numbers in
    `docs/EVAL_BASELINE.md`. Not in CI because it costs money,
    but `make eval` runs it on demand and pre-merge.

## Talking points (for the grill)

1. **"Right tier for the job."** Haiku on the per-message hot path,
   Sonnet later for the writing. Cost matches usage.
2. **"Structured output is non-negotiable."** Pydantic strict +
   single retry + fallback. The pipeline can't be hostage to LLM
   prose drift.
3. **"Tool use, not RAG dump."** The agent decides when it needs
   thread context. Average call doesn't fetch — only the ambiguous
   ones do. That keeps p50 latency under 1.5s.
4. **"Eval baseline, not vibes."** Hand-labelled fixtures with
   accuracy thresholds. Prompt changes ship with a baseline diff.
5. **"Always write the tag row."** Even on fallback. No silent
   drops. Audit trail intact.
6. **"Idempotent at the task level."** `messages.UNIQUE(source,
   external_id)` and `message_tags.UNIQUE(message_id)`. Retries
   from Celery don't double-write.
