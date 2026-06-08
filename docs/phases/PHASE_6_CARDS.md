# Phase 6 — Knowledge Cards

## Goal

Knowledge Cards are the atomic unit of the product — every decision,
risk, and open question is a Card. This phase builds the create path:
when the Router agent (Phase 5) flags `should_create_card=true`, a
Celery task `build_card` loads the message + thread context via MCP,
calls Sonnet to draft a Card body, persists `cards` + `card_sources`
rows, and publishes an SSE event. It also ships the read API:
`GET /api/v1/cards?project_id=...` for the list and
`GET /api/v1/cards/{id}` for the expanded detail with sources.

Updates to existing Cards are *not* in scope — for the take-home a
Card is created once and stays as-is. Editing / re-summarising on
later messages is in the roadmap.

## Why this phase, this order

Phase 5 produces the signal ("this message is a decision candidate
about ECO-178, summarise it"). Phase 6 turns that signal into the
durable, citable artefact the UI renders. Without Phase 6 the Router
agent's `should_create_card=True` is a dead-end flag.

It comes after Phase 5 because the input shape (a `Message` plus a
`summary_hint` plus a `card_kind`) is what the Router emits. It comes
before Phase 7 (Scoring) and Phase 8 (Digest) because both of those
read from `cards` — scoring boosts items linked to open Cards, and
the Digest agent cites Cards in the morning briefing. And it has to
land before Phase 9 (Dashboard FE) because the dashboard renders
Cards as the primary unit on screen.

Order inside the phase: schema → repository → builder + prompt →
Celery task → API endpoints → tests.

## Pre-requisites

- Phase 2 (RLS: `cards.org_id` filtered by session setting)
- Phase 4 (MCP tools: `get_thread_context` for the builder)
- Phase 5 (Router enqueues `build_card`, and `messages` rows exist)
- `llm/tiering.py` exposes `sonnet()` returning the configured
  Sonnet 4.6 model id
- DB schema already declared in Phase 3: `cards`, `card_sources` (no
  DDL in this phase)

## Files touched

### New

- `apps/api/src/evercurrent/cards/__init__.py`
- `apps/api/src/evercurrent/cards/builder.py` — Sonnet-driven body
  drafting
- `apps/api/src/evercurrent/cards/schemas.py` — `CardDraft`,
  `CardSourceRef`, `CardResponse`, `CardListItem`
- `apps/api/src/evercurrent/cards/repository.py` — `cards` +
  `card_sources` reads / writes
- `apps/api/src/evercurrent/cards/service.py` — service layer for the
  API routes
- `apps/api/src/evercurrent/cards/prompts/draft_card.txt`
- `apps/api/src/evercurrent/api/routers/cards.py` — GET endpoints
- `apps/api/tests/integration/cards/test_builder.py`
- `apps/api/tests/integration/cards/test_build_card_task.py`
- `apps/api/tests/integration/cards/test_repository.py`
- `apps/api/tests/integration/cards/test_api.py`

### Modified

- `apps/api/src/evercurrent/jobs/celery_tasks.py` — replace the stub
  `build_card` from Phase 5 with the real task
- `apps/api/src/evercurrent/main.py` — register the cards router
- `apps/api/src/evercurrent/db/models.py` — add a unique-ish
  constraint via Alembic migration (see Tasks #2)
- `apps/api/alembic/versions/<new>_card_idempotency.py` — partial
  unique index on `(message_id, kind)` via `card_sources` (see #2)

### Deleted

- nothing

## Tasks

1. **Schemas** (`cards/schemas.py`):
   - `CardDraft`:
     ```python
     class CardDraft(BaseModel):
         model_config = ConfigDict(strict=True, frozen=True)
         summary: str = Field(min_length=10, max_length=200)
         body: str = Field(min_length=20)
         affected_subsystems: list[str]
         confidence: float = Field(ge=0.0, le=1.0)
         decided_at: datetime | None
     ```
     Cross-field validator: `decided_at` only allowed when the
     `kind` passed alongside is `"decision"`.
   - `CardSourceRef { source_kind: Literal["message","document_chunk",
     "pr"], source_id: UUID, snippet: str | None }`
   - `CardResponse` (full detail returned by `GET /cards/{id}`):
     `id`, `kind`, `summary`, `body`, `status`, `confidence`,
     `decided_at`, `affected_subsystems`, `sources: list[
     CardSourceRef]`, `created_at`, `updated_at`.
   - `CardListItem` (compact, returned by `GET /cards`): `id`,
     `kind`, `summary`, `status`, `confidence`, `decided_at`,
     `sources_count`, `updated_at`.
2. **Idempotency migration.** New Alembic migration:
   partial unique index that prevents two cards being created from
   the same triggering message + kind. The natural place is a join
   row: add `triggering_message_id UUID` to `cards` (nullable, FK to
   `messages` ON DELETE SET NULL), and create:
   ```sql
   CREATE UNIQUE INDEX cards_triggering_message_kind_uidx
     ON cards (triggering_message_id, kind)
     WHERE triggering_message_id IS NOT NULL;
   ```
   This means if Celery retries `build_card(msg, "decision")`, the
   second insert raises `IntegrityError`; the task catches it,
   no-ops, returns the existing card id.
3. **Repository** (`cards/repository.py`):
   - `async create_card(draft: CardDraft, *, kind: str,
     project_id: UUID, triggering_message_id: UUID) -> Card`
   - `async add_sources(card_id: UUID, refs: list[CardSourceRef]) ->
     None`
   - `async list_cards(project_id: UUID, kind: str | None,
     status: str | None) -> list[CardListItem]`
   - `async get_card(card_id: UUID) -> CardResponse | None` —
     joins `card_sources` and resolves each `source_id` into a
     snippet (for messages: first 200 chars; for document_chunks:
     section + first 200 chars).
   - `async get_existing(triggering_message_id: UUID, kind: str) ->
     Card | None`
4. **Builder** (`cards/builder.py`). Class `CardBuilder`:
   ```python
   async def build(self, message_id: UUID, kind: str,
                    summary_hint: str) -> Card
   ```
   Flow:
   1. Idempotency check: `repo.get_existing(message_id, kind)`. If
      it exists, return it.
   2. Load the message + thread context via
      `mcp_client.call("get_thread_context",
      {"message_id": message_id})`.
   3. Load the author membership via
      `get_user_context(membership_id=message.author_membership_id)`.
   4. Render `draft_card.txt` prompt with: message text, thread
      snippet, author role, `kind`, `summary_hint`, project phase.
   5. Call Sonnet via `llm.sonnet.create()`. No tool use here — the
      builder has already gathered context. Sonnet just writes.
   6. Parse the response into `CardDraft`. Pydantic strict. On
      `ValidationError`, retry once with a schema reminder. On
      second failure, log and raise — the Celery task will retry
      with backoff (this is a write path; we don't fallback-write
      a bad Card).
   7. `repo.create_card(draft, kind, project_id, message_id)`.
   8. Build source refs: triggering message + every reply in the
      thread (deduped) → `repo.add_sources(card_id, refs)`.
5. **Celery task `build_card`** in `jobs/celery_tasks.py`:
   ```python
   @celery_app.task(name="build_card", bind=True, max_retries=3,
                    autoretry_for=(TransientLLMError,),
                    retry_backoff=True)
   def build_card(self, message_id: UUID, kind: str,
                   summary_hint: str) -> None: ...
   ```
   Body:
   1. Set RLS context for the org of the message.
   2. `await builder.build(message_id, kind, summary_hint)`.
   3. Publish `events:<org_id>` SSE event:
      `{type: "card_created", payload: {card_id, kind, summary,
       project_id}}`. After the commit.
   4. Write `audit_log` row with model + tokens + latency.
6. **Prompt** (`cards/prompts/draft_card.txt`). Instructions:
   - You are drafting a Knowledge Card of kind `{kind}`.
   - Summary: one sentence, decisive voice.
   - Body: 3–6 sentences, structure varies by kind:
     - decision: what was decided, why, who, what it affects.
     - risk: what could go wrong, what triggers it, who owns
       mitigation.
     - question: what is the open question, who needs to answer,
       what's blocking it.
   - List `affected_subsystems` as 0–3 short tags from a fixed
     vocabulary (passed in the prompt as project phase concerns).
   - `confidence`: how sure you are this is a real Card vs noise.
   - `decided_at`: only if kind=decision and the message clearly
     marks a decision time; otherwise null.
   - Output JSON matching the schema.
7. **API endpoints** (`api/routers/cards.py`):
   - `GET /api/v1/cards` — query params `project_id` (required),
     `kind`, `status`. Pagination `limit` (default 50, max 200),
     `cursor` (updated_at, id). Returns `list[CardListItem]`.
   - `GET /api/v1/cards/{id}` — returns `CardResponse` with
     expanded sources. 404 if not in current org (RLS handles it).
   - Both endpoints depend on `get_current_user` + RLS middleware.
8. **Tests**:
   - `test_repository.py` — direct repo calls against testcontainers
     Postgres. Create card, add sources, list, get. Assert
     idempotency: two `create_card` calls with same
     `(triggering_message_id, kind)` raise `IntegrityError`.
   - `test_builder.py` — mock Sonnet to return a canned `CardDraft`
     JSON. Cases:
     - happy path: card + sources written.
     - idempotency: call `build` twice, second returns the existing
       card, Sonnet called only once.
     - schema-drift: invalid JSON once → retry succeeds.
     - second failure: assert raises (no fallback write).
   - `test_build_card_task.py` — invoke Celery task synchronously.
     Mock builder. Assert SSE event published *after* the DB
     commit. Assert idempotency at the task level (retry with same
     args yields one card).
   - `test_api.py` — boot test client, seed two orgs each with
     cards, call `GET /api/v1/cards?project_id=...` as a user in
     org A, assert org B's cards never appear. Same for
     `GET /api/v1/cards/{id}` with org B's card id → 404.
9. **structlog events**:
   - `cards.build` with `card_id`, `kind`, `confidence`, `tokens`,
     `latency_ms`.
   - `cards.idempotent_hit` when `get_existing` returns a row.
10. **Lint + test.** `make lint && make test-integration` green.
11. **Commit.** `feat(phase-6): knowledge cards — Sonnet drafting,
    sources, idempotent builder, read API`.

## Test plan

TDD, written before the implementation files:

1. `test_repository.py` first — proves the schema + idempotency
   constraint work before any LLM is involved.
2. `test_builder.py` — mocks Sonnet, exercises the agent flow
   including the retry path.
3. `test_build_card_task.py` — end-to-end Celery task with mocked
   Sonnet + mocked Redis publisher. Asserts publish-after-commit
   ordering by checking the publisher is called *after* a DB query
   confirms the row.
4. `test_api.py` — read endpoints, including cross-org isolation.

Eval coverage of Card *quality* is part of the Digest eval (Phase 8)
since the Digest cites Cards; we don't ship a separate "is this Card
good?" eval here.

## Definition of done

- [ ] `CardDraft` schema strict + cross-field validator
- [ ] Alembic migration adds `triggering_message_id` + partial
      unique index, runs cleanly on a fresh DB
- [ ] `CardBuilder.build` is idempotent: second call with same
      `(message_id, kind)` returns the existing card, no second LLM
      call
- [ ] `build_card` Celery task wired: load → draft → persist →
      SSE publish-after-commit → audit log
- [ ] `GET /api/v1/cards` returns `CardListItem` rows filtered by
      query params
- [ ] `GET /api/v1/cards/{id}` returns `CardResponse` with sources
      expanded
- [ ] RLS holds: org B cannot read org A cards (API test)
- [ ] All four test files green in CI
- [ ] One commit on `feat/phase-6-cards` branch, merged to `main`

## Common pitfalls

- **Building the Card without thread context.** A "we'll ship
  Tuesday" message in isolation is a status update; in a thread
  about ECO-178 sign-off it's a decision. The builder *always*
  pulls thread context before calling Sonnet — even though it costs
  one MCP call — because the summary quality collapses without it.
- **Idempotency via "check then insert".** Race condition: two
  Celery workers pick up retries simultaneously, both see no row,
  both insert. Use the unique index + catch `IntegrityError`. The
  DB is the source of truth, not application logic.
- **Publishing SSE before commit.** Browser invalidates a query,
  refetches, and the new card isn't there yet. Order: commit →
  publish. In tests, mock the publisher and assert call ordering
  relative to a `SELECT` that confirms the row exists.
- **Fallback-writing a bad Card.** Unlike Phase 5 where we write
  a "uncategorized" tag row to keep the audit trail, here we don't
  want a garbage Card polluting the dashboard. On second
  validation failure, raise and let Celery retry with backoff.
- **Letting `affected_subsystems` be free text.** The Digest agent
  and the scoring engine both filter on these. If Sonnet invents
  a new tag every call ("chassis-bracket", "bracket-chassis",
  "chassis_bracket"), filters break. Pass the project's known
  subsystem list into the prompt and ask Sonnet to pick from it,
  with an "other" escape hatch.
- **`card_sources` as JSONB on `cards`.** Tempting (one fewer
  table), but you lose the ability to query "what cards cite this
  message?" cheaply. Keep `card_sources` as its own table with
  indexes on `card_id` and `(source_kind, source_id)`.
- **Forgetting to update `cards.updated_at`.** This phase only
  creates, so `updated_at == created_at`, but the read API sorts
  by `updated_at DESC`. Set a default and a `onupdate` so when
  Phase 13 (Card updates, roadmap) lands, the ordering already
  works.

## Recap — what you'll be able to explain after this phase

- "Why are Cards first-class instead of a view over messages?"
  → Every decision, risk, and question becomes a durable, citable,
    scoreable object. Slack threads die. PDFs get superseded. PRs
    merge. The Card outlasts them and points back at sources. The
    dashboard, morning digest, future timeline, and future chat
    answers all anchor on Cards. A view over messages couldn't
    carry cross-source citations (message + PDF chunk + PR) and
    couldn't track status (open → closed) independent of chatter.
- "Why is source citation a separate table, not JSONB on `cards`?"
  → Cards have N sources of mixed kinds (message, document_chunk,
    PR). A separate table with `(source_kind, source_id)` makes
    "what cards cite this document?" a one-index query.
    JSONB would force a scan. It also keeps the Card row small
    so the list endpoint stays fast.
- "How do you handle a duplicate `build_card` call?"
  → Idempotency at the DB level: partial unique index on
    `(triggering_message_id, kind)`. The builder tries to insert,
    catches `IntegrityError`, returns the existing row. Celery
    retries are safe. No race window — the DB arbitrates.
- "Why mark `confidence` on a Card?"
  → The agent is making a judgement call ("is this really a
    decision, or just chatter?"). Persisting confidence lets the
    UI grade the badge, lets the Digest agent demote low-confidence
    Cards, and lets us tune the prompt by looking at the bottom
    quartile.
- "Why does the builder use Sonnet, not Haiku?"
  → Drafting prose is where Sonnet's quality lift over Haiku is
    visible. Cost is bounded because this only runs when the
    Router decided "yes, this deserves a Card" — much rarer than
    the per-message Router call.
- "What about updates when a later message changes things?"
  → Roadmap. For take-home scope, Cards are immutable after
    creation. Next iteration: builder detects "a new message in
    this thread materially changes the Card" and runs a Sonnet
    pass to update `body` + bump `updated_at`. Punted because the
    immutable case proves the architecture; the update case needs
    a "what counts as material" prompt + eval we don't have time
    for.

## Talking points (for the grill)

1. **"Atomic unit of awareness."** Cards are the thing every screen
   anchors on. Decisions, risks, questions — same shape, same table,
   same source model.
2. **"Idempotent at the DB."** Partial unique index +
   `IntegrityError` catch. Race-safe, retry-safe.
3. **"Sources are first-class."** Separate table, mixed kinds,
   queryable both ways (cards → sources, sources → cards).
4. **"Sonnet earns its tier here."** Drafting prose, not
   classification. The per-Card cost is bounded by the Router's
   `should_create_card` filter.
5. **"Confidence is persisted."** Surfaces uncertainty in the UI;
   feeds the Digest's ranking; gives us a knob for prompt tuning.
6. **"Publish-after-commit on SSE."** Ordering matters. Browser
   never sees an event for a row that isn't there yet.
7. **"Immutable today, updateable on the roadmap."** Scope was
   chosen so the architecture is provable now, the next iteration
   slots in without a refactor.
