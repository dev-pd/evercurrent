# Phase 8 — Digest agent

## Goal

The hero feature. Every morning, at 8am in each user's local timezone,
Sonnet drafts a personalised briefing for that user from the top-N
scored items, their member profile, the project's open Cards affecting
their subsystems, and the prior three days' digests for continuity.
The output is markdown plus a structured list of cited `card_ids` and
`message_ids`. The row is persisted as one `digests` row per
`(project_member_id, day_index)`. SSE notifies the dashboard the
moment it lands.

This is the single feature most of the demo hinges on. Router + Cards
+ Scoring all earned their place; this is what the user actually sees.

## Why this phase, this order

By phase 7 we have tags, cards, and per-user scores. We have everything
the digest needs as *inputs*. The only thing missing is the agent that
turns those inputs into prose with citations.

We do the digest as a per-user nightly batch instead of regen-on-message
because (a) it's the cheapest path to one polished briefing per user
per day, (b) it's idempotent — `(member, day)` is unique so re-runs
are safe, and (c) the user only reads it once. Streaming a fresh
digest every time a message lands would be wasteful, distracting, and
hard to make coherent.

Sonnet, not Haiku, for the writing. The digest is the one place in
the system where prose quality matters more than per-call cost — it
runs at most once per user per day, and a generic-feeling briefing
fails the product even if every fact is right.

The order inside the phase: schemas first (so the agent has typed
output), prompt + Jinja template second, scheduler third (Beat is
finicky), agent body fourth (calls the LLM and parses output),
persistence + SSE fifth, regen endpoint last.

## Pre-requisites

- Phase 5 (router) writing `message_tags`
- Phase 6 (cards) writing `cards` + `card_sources`
- Phase 7 (scoring) writing `scores` rows for every member of every
  active project
- Celery worker + Celery Beat both running (phase 1 infra)
- `org_memberships.timezone` populated for every member
- `projects.current_phase` populated
- `llm/client.py` Sonnet helper available (locked May 2026:
  `claude-sonnet-4-6`)

## Files touched

### New
- `apps/api/src/evercurrent/digest/__init__.py`
- `apps/api/src/evercurrent/digest/schemas.py` — `DigestContext`,
  `DigestDraft`, `DigestItem`, `SectionBucket`
- `apps/api/src/evercurrent/digest/agent.py` — `draft_digest(ctx) -> DigestDraft`
- `apps/api/src/evercurrent/digest/prompts/system.txt`
- `apps/api/src/evercurrent/digest/prompts/user.txt.j2`
- `apps/api/src/evercurrent/digest/scheduler.py` — Beat helper
  `members_due_at(now_utc) -> list[membership_id]`
- `apps/api/src/evercurrent/digest/repository.py` — persist,
  fetch-latest, idempotency check
- `apps/api/src/evercurrent/digest/service.py` —
  `generate_digest_for_member(membership_id, day_index, force=False)`
- `apps/api/src/evercurrent/api/routers/digests.py` —
  `GET /api/v1/digests/today`, `POST /api/v1/digests/regenerate`
- `apps/api/tests/unit/digest/test_scheduler.py`
- `apps/api/tests/unit/digest/test_idempotency.py`
- `apps/api/tests/unit/digest/test_persistence.py`
- `apps/api/tests/evals/digest/scenarios/` — seeded scenario JSONs
- `apps/api/tests/evals/digest/test_quality.py` — LLM-as-judge harness

### Modified
- `apps/api/src/evercurrent/jobs/celery_tasks.py` — add
  `generate_digest_for_member(membership_id, day_index, force)`
- `apps/api/src/evercurrent/jobs/celery_app.py` — add Beat schedule:
  every-minute scan task `scan_and_enqueue_due_digests`
- `apps/api/src/evercurrent/main.py` — register `digests` router
- `apps/api/src/evercurrent/db/models.py` — confirm `Digest` model

### Deleted
- nothing

## Tasks

1. **Schemas.** `digest/schemas.py`:
   ```python
   class DigestItem(BaseModel):
       model_config = ConfigDict(strict=True)
       message_id: UUID | None
       card_id: UUID | None
       bucket: Literal["top_priority", "watch_outs", "fyi"]
       why_this_matters: str
       source_summary: str

   class DigestDraft(BaseModel):
       content_md: str
       cited_message_ids: list[UUID]
       cited_card_ids: list[UUID]
       items: list[DigestItem]
       section_buckets: dict[str, list[int]]  # bucket -> item indices

   class DigestContext(BaseModel):
       member: MemberProfile
       project: ProjectSnapshot
       top_scored_items: list[ScoredItem]   # up to 20
       open_cards: list[CardSummary]
       prior_digests: list[PriorDigest]     # last 3 days, markdown only
   ```
2. **Prompts.** `digest/prompts/system.txt`: voice + format rules
   (second person, no greetings beyond opening line, citations as
   inline references, length budget 250–400 words, three buckets).
   `digest/prompts/user.txt.j2`: Jinja2 template renders the
   `DigestContext` into a structured payload.
3. **Agent body.** `digest/agent.py`:
   - `draft_digest(ctx: DigestContext) -> DigestDraft`
   - Render prompts, call `llm.client.sonnet(...)` with available
     MCP tools: `search_messages`, `query_cards`, `get_thread_context`
     for selective expansion. Agent decides whether to call them.
   - Use Anthropic's response-format / tool-use loop; cap at 4
     iterations. Parse final message into `DigestDraft` via Pydantic.
   - Log model name, input tokens, output tokens, latency, tool-call
     count via structlog.
4. **Scheduler.** `digest/scheduler.py`:
   - `members_due_at(now_utc) -> list[UUID]`: for each active
     membership, compute its local time from `tz`. Return memberships
     whose local time falls inside `[08:00, 08:05)`. The 5-minute
     window matches the every-minute Beat scan and tolerates clock
     skew without double-firing thanks to idempotency.
   - `day_index_for(membership, now_utc) -> int`: days since
     `project.start_date` in the member's local timezone.
5. **Beat task + per-user task.** `jobs/celery_tasks.py`:
   ```python
   @app.task(name="scan_and_enqueue_due_digests")
   def scan_and_enqueue_due_digests() -> None:
       for mid in scheduler.members_due_at(utcnow()):
           generate_digest_for_member.delay(str(mid),
               day_index=scheduler.day_index_for(mid, utcnow()))

   @app.task(name="generate_digest_for_member")
   def generate_digest_for_member(membership_id: str,
                                  day_index: int,
                                  force: bool = False) -> None:
       asyncio.run(service.generate(UUID(membership_id), day_index, force))
   ```
   Beat schedule: `scan_and_enqueue_due_digests` every 60 seconds.
6. **Service.** `digest/service.generate`:
   - Idempotency check: if `(project_member_id, day_index)` row
     exists and `force is False`, return early. No work, no Sonnet
     call, no SSE.
   - Build `DigestContext` via repositories: profile, top-20 scores
     join messages + message_tags, open Cards filtered by
     `affected_subsystems` intersection with member's owned, last 3
     digests' markdown.
   - Call `agent.draft_digest(ctx)`.
   - Persist via `repository.upsert(...)`.
   - Publish to Redis: `events:<org_id>` →
     `{type: "digest_ready", payload: {digest_id, day_index}}`.
7. **Routers.** `api/routers/digests.py`:
   - `GET /api/v1/digests/today`: latest row for the principal's
     membership in the active project. 404 if none yet.
   - `POST /api/v1/digests/regenerate`: enqueue
     `generate_digest_for_member(..., force=True)`, return `{job_id}`.
8. **Eval scenarios.** `tests/evals/digest/scenarios/`: 5 hand-built
   JSONs — seeded messages + scored items + expected leading topics
   and citations. Each scenario lists must-cite IDs and must-include
   topics; the LLM judge rates coverage, second-person voice,
   citation accuracy.
9. **Run.** `make test-unit && make eval-digest`. Eval is not a CI
   gate; numbers land in `docs/EVAL_BASELINE.md`.
10. **Commit.** `feat(phase-8): digest agent — per-user 08:00-local briefing`.

## Test plan

Two layers: deterministic plumbing tests (Vitest-style unit tests on
the parts that don't call Sonnet) and an LLM-as-judge eval harness
(the parts that do).

Deterministic (unit) tests — must pass in CI:

- `test_beat_schedule_emits_one_task_per_member_at_8am_local` —
  scheduler with three members in UTC, PST, JST at fixed UTC time
  produces exactly one task each at the right moment, none outside
  the window.
- `test_scheduler_window_does_not_double_fire` — running
  `members_due_at` for two consecutive minutes inside the 5-minute
  window yields the same membership both times; idempotency in
  `service.generate` blocks the second from doing work. Asserts the
  second call short-circuits.
- `test_digest_idempotent_on_same_member_day` — call `service.generate`
  twice with `force=False`; second call returns the existing row, no
  LLM call, no SSE event.
- `test_force_regen_replaces_existing` — first call writes row; second
  with `force=True` overwrites `content_md` and `generated_at`. The
  `(member, day)` row count stays at 1.
- `test_persisted_row_has_citations` — given a stubbed
  `DigestDraft` from the agent, the repository writes `card_ids`
  and `message_ids` UUID arrays matching the draft. Round-trip test.
- `test_score_query_returns_top_N_for_member` — fixture with 30
  `scores` rows for one member; `repository.top_scored_items(...,
  limit=20)` returns exactly 20, ordered by `score DESC`. Locks the
  query the digest depends on.
- `test_open_cards_filtered_to_member_subsystems` — member owns
  `[chassis]`; fixtures include 3 cards affecting chassis + 2
  affecting only firmware; query returns the 3 chassis ones.
- `test_day_index_uses_member_timezone` — project starts Jun 5; on
  Jun 7 14:00 UTC, PST member's day_index is 2; JST member's is 3.
- `test_regenerate_endpoint_returns_job_id` — route hits service,
  returns a job id; idempotency guard inside still holds.

Eval (LLM-as-judge) — `make eval-digest`, not in CI:

- 5 seeded scenarios with hand-curated `must_cite_card_ids` and
  `must_cite_message_ids`. Judge rubric (Sonnet):
  - **Relevance** (1–5): does the digest lead with what the rubric
    says is top priority?
  - **Citation accuracy** (1–5): every claim cites a real source
    from the input set; no hallucinated IDs.
  - **Voice** (1–5): second person, terse, no greeting bloat.
  - **Length budget** (binary): 250–400 words.
- Aggregate scored and recorded to `docs/EVAL_BASELINE.md`.

What we deliberately do NOT unit-test: the LLM output prose itself.
That's the eval's job. Fighting Sonnet with `assert "Top priority" in
output` is brittle and useless.

## Definition of done

- [ ] `make test-unit` passes (all deterministic tests above)
- [ ] `make eval-digest` runs end-to-end on 5 scenarios and emits a
      score JSON to `docs/EVAL_BASELINE.md`
- [ ] Celery Beat schedule `scan_and_enqueue_due_digests` registered
      at 60-second cadence
- [ ] For a seeded member with timezone PST and project start 3 days
      ago, manually running `scan_and_enqueue_due_digests` at the
      right UTC time produces exactly one `digests` row
- [ ] `GET /api/v1/digests/today` returns the row with citations
- [ ] `POST /api/v1/digests/regenerate` overwrites and broadcasts
      SSE `digest_ready`
- [ ] Per-digest cost on a 20-item context is under $0.05 (logged)
- [ ] End-to-end latency on the per-user task under 8 seconds
- [ ] `make lint` clean
- [ ] One commit on `feat/phase-8-digest` branch, merged to `main`

## Common pitfalls

- **Beat scanning every minute but window is 5 minutes →
  five-of-a-kind fires.** Idempotency on `(member, day)` is the
  catch. Don't try to be clever with the window; let the unique
  constraint do its job.
- **Local-time computation drift.** Always store `timezone` as IANA
  string (`America/Los_Angeles`), never as UTC offset. DST will
  bite you in March if you persist `-08:00`. Use
  `zoneinfo.ZoneInfo`.
- **Citations that don't appear in input.** Sonnet sometimes invents
  IDs that look plausible. Validate every cited ID against the input
  set in the service layer before persisting; drop hallucinated
  citations and log a warning.
- **Prompt in Python source.** No. Prompts live in
  `digest/prompts/*.txt`. Code reads them via `importlib.resources`
  or a thin `load_prompt(name)` helper.
- **Sonnet streams; service wants whole response.** Use the
  non-streaming `messages.create` for the digest. Streaming is for
  the dashboard chat (roadmap), not for a batch agent persisting a
  row.
- **Storing the LLM payload as raw text.** Persist parsed schema
  fields too. Otherwise the dashboard has to re-parse markdown to
  highlight which sources go in which bucket.
- **`force=True` on every regen click.** The endpoint accepts a
  user-initiated force, but the route should rate-limit per
  membership (one regen per minute). Otherwise a stuck refresh
  loop melts the LLM budget.
- **Day index off-by-one across DST.** Compute it as "calendar days
  in member's tz since project start," not "hours / 24."

## Recap — what you'll be able to explain after this phase

- "Why precompute the digest nightly instead of regenerating on every
  new message?" → Cost (one Sonnet call per user per day, not per
  message), idempotency (`(member, day)` is unique, replay-safe),
  and the user-reading model — the digest is consumed once around
  8am, not continuously.
- "Why store one row per `(member, day)`?" → Audit (you can show
  last week's digests verbatim), replay safety (Celery retries are
  no-ops), and historical UX ("show me Monday's").
- "Why Sonnet here, not Haiku?" → Writing quality is the product.
  This is the user's first impression every morning. The cost
  difference at one call per user per day is negligible — about
  $0.04 vs $0.005 — and the prose quality difference is large.
- "How do you handle 200 users in 200 timezones?" → Beat scans every
  minute; the scan task asks the scheduler "who is at 08:00 local
  right now?" and enqueues a small fanout. Worker concurrency
  handles the bursts. No per-user Beat entries.
- "What stops a double-digest if the worker restarts mid-run?" →
  Idempotency on `(project_member_id, day_index)`. The service
  short-circuits before any LLM call if the row exists and
  `force is False`.
- "How do you measure digest quality?" → Eval harness with
  LLM-as-judge on hand-built scenarios. Five rubric dimensions.
  Numbers live in `docs/EVAL_BASELINE.md`. Not a CI gate —
  reference numbers we move deliberately.

## Talking points (for the grill)

1. **"The digest is the hero."** Everything before this phase
   exists to feed it. Tags, cards, scores — all upstream inputs.
2. **"Per-user, per-day, precomputed."** Each property earns its
   keep: per-user enables personalisation, per-day enables history,
   precomputed enables sub-second read.
3. **"Sonnet for writing, never Haiku."** Cost economics support it
   (1 call / user / day), and the prose is the product.
4. **"Idempotency from the schema up."** UNIQUE on `(member, day)`
   plus the service guard means restarts and Beat overlaps are
   harmless.
5. **"Timezones via IANA + zoneinfo."** DST-safe.
6. **"Tool-use loop with a cap."** The agent can search for thread
   context to expand an item, but we cap iterations at 4. Agentic,
   not runaway.
7. **"Citations validated against input set."** No hallucinated
   `message_id`s reach the database.
8. **"Eval harness with LLM-as-judge."** Five rubric scores per
   scenario, baseline recorded, regressions visible.
