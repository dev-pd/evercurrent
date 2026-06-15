# EverCurrent — Backend System Design

A walkthrough of how the system actually works, end to end, with
file:line anchors into the code. Written for someone who needs to
explain or defend the design (the code is the source of truth — if a
detail here drifts from the code, the code wins).

`docs/ARCHITECTURE.md` covers the layering rationale. This document
covers the **runtime flows**: how a Slack message becomes a
personalized digest item, how digests are generated, how
personalization adapts, and how the UI stays live.

---

## 1. What the product does

EverCurrent is a multi-tenant B2B SaaS that gives each member of a
hardware-engineering team a **personalized daily digest** built from
their Slack chatter and spec documents. The same firehose of messages
produces a *different* digest for the mechanical lead, the power
electronics engineer, and the QA owner — ranked by **role**,
**owned subsystems**, **project phase**, and the member's own
**feedback over time**. On top of the digest:

- **Decisions log** — structured decision/risk/question cards extracted
  from chatter.
- **Eve** — a proactive agent that surfaces cross-subsystem conflicts
  (e.g. spec says X, chatter says Y).
- **View-as** — see the entire app through any member's eyes.

---

## 2. The shape of the system

```
                    ┌──────────────────────────────────────────────┐
   Slack workspace  │  FastAPI (apps/api)         Next.js (apps/web)│
   ────────────────▶│  ┌────────────┐             ┌───────────────┐ │
   Events API       │  │  routes/   │◀── proxy ───│ App Router    │ │
   (webhook)        │  │  (HTTP)    │   (JWT)      │ server comps  │ │
                    │  └─────┬──────┘             └───────┬───────┘ │
                    │        │ enqueue                     │ SSE     │
                    │  ┌─────▼──────┐             ┌────────▼──────┐  │
                    │  │  Celery    │── publish ─▶│ Redis pub/sub │  │
                    │  │  worker    │             └───────────────┘  │
                    │  │  + Beat    │                                │
                    │  └─────┬──────┘                                │
                    │        │                                       │
                    │  ┌─────▼───────────────────────────────────┐  │
                    │  │ Postgres 17 + pgvector  (RLS per org)    │  │
                    │  └─────────────────────────────────────────┘  │
                    └──────────────────────────────────────────────┘
```

- **Routes → services → repositories → DB.** No SQL in routes, no HTTP
  in services (AGENTS.md §5).
- **All heavy work is async** on Celery. HTTP handlers stay non-blocking
  — they enqueue and return.
- **Every row is org-scoped** via Postgres Row-Level Security. The app
  connects as a restricted role and sets `app.current_org_id` per
  transaction; the DB enforces isolation, not application code.

---

## 3. Flow A — a Slack message becomes a digest item

This is the ingestion pipeline. It is **fully asynchronous and
idempotent** — every stage can be replayed safely.

```
Slack ──▶ webhook ──▶ raw_events ──▶ route_message ──▶ messages
                       (dedup)          │  ├─▶ message_tags   (Haiku)
                                        │  ├─▶ build_card     (Sonnet) ──▶ cards
                                        │  └─▶ score_message  (pure code) ──▶ scores
                                        └─▶ publish "message_tagged" (SSE)
```

### Step by step

1. **Webhook receives the event.** `api/routes/webhooks.py:151`
   (`slack_webhook`) → `connectors/slack/events.py:66` (`handle_event`).
   - HMAC-SHA256 signature verified with a 5-minute timestamp window
     (`connectors/slack/events.py:37` `verify_signature`). Rejects
     replays and forgeries.
   - First-time `url_verification` challenge is echoed back
     (`events.py:78`).
2. **Tenant resolution.** Look up the `Connector` row by
   `external_team_id` (the Slack workspace id) → gives `org_id`
   (`events.py:100`). `set_org_context(session, org_id)`
   (`tenancy/rls.py`) pins RLS for everything downstream.
3. **Dedup at the door.** Insert into `raw_events` with
   `ON CONFLICT (source, external_id) DO NOTHING`
   (`events.py:159` `_persist_raw_event`). Slack's `event.ts` is the
   natural key. A re-delivered event inserts nothing and stops here —
   **this is what makes the webhook safe to retry.**
4. **Enqueue + return 200 fast.** Only on a *new* raw event do we
   enqueue `evercurrent.route_message` (`events.py:125`,
   `connectors/slack/tasks.py:12`). The HTTP response returns
   immediately; Slack never waits on the LLM.
5. **`route_message` worker** (`jobs/tasks/route_message.py:406`):
   - **Upsert the message** (`_upsert_message:61`) —
     `ON CONFLICT (source, external_id) DO NOTHING`, resolves the
     single project for the org, returns `(message_id, project_id)`.
     Threads are linked by joining the parent's `external_id`
     (thread_ts).
   - **Build router context** — author role from `org_memberships`
     (`_resolve_author_role:151`), thread parent text, current project
     phase.
   - **Tag with Haiku** — `routing/router_agent.py:110` (`classify`)
     calls the LLM (tier = tagging, temp 0.0, prompts in
     `routing/prompts/`) and returns a strict `RouterDecision`:
     `topic, urgency, entities, affected_roles, should_create_card,
     card_kind`. On parse failure it retries once, then falls back to a
     safe default (`routing/schemas.py` `fallback_decision`).
   - **Write the tag** — `message_tags` upsert (`_write_tag:191`).
   - **Fan out** (`_enqueue_followups:227`): always enqueue
     `score_message_for_members`; enqueue `build_card` only if the
     router said `should_create_card`.
   - **Publish** `message_tagged` to the project's SSE channel
     (`route_message.py:371`).
6. **`build_card` worker** (`jobs/tasks/build_card.py:33` →
   `cards/builder.py:178`): idempotency check on `(message_id, kind)`,
   pulls full thread context, drafts a `decision | risk | question`
   card with Sonnet, inserts into `cards`, records sources, publishes
   `card_created`.
7. **`score_message_for_members` worker** — see Flow C. This is the
   step that makes the message *personalized*: it computes one score
   per member.

### Backfill (already-posted history)

A live webhook only catches *new* messages. To pull history when a
workspace first connects: `jobs/tasks/sync_slack.py` discovers channels
and calls `connectors/slack/backfill.py:29` (`backfill_channel`), which
pages `conversations.history` + `conversations.replies` and runs each
message through the **same** `raw_events`/`route_message` path. So
history and live traffic converge on one pipeline.

> **Gotcha worth knowing:** Slack's `oldest` cursor must be an integer
> epoch string, not a float (`"1778880037"` not `"1778880037.95"`), or
> the API silently returns zero messages. Fixed in `backfill.py`.

---

## 4. Flow B — how a digest gets generated

Two triggers, **one task**: `generate_digest_for_member`.

### Trigger 1 — scheduled (the real product behavior)

- **Celery Beat** runs `enqueue_due_digests_now` every 60 seconds
  (`jobs/celery_app.py:26`).
- The scan (`digest/scheduler.py`) walks active memberships, converts
  `now` into each member's timezone, and enqueues a digest for anyone
  whose local time is in the **08:00–08:05 window** (`members_due_at`).
  `day_index` is computed from the project `start_date`; phase from
  `projects.current_phase`.
- So digests arrive at 8am *local* per member, once per day. The
  per-(member, day_index) unique constraint makes the minute-by-minute
  scan safe — a second enqueue for the same day is a no-op upsert.

### Trigger 2 — on-demand (the Regenerate button)

- `POST /api/v1/digests/regenerate` (`api/routes/digests.py:166`)
  enqueues the same task with `force=True` and returns **202 +
  job_id** immediately. It does *not* wait ~20s for the LLM.

### The task itself (`jobs/tasks/generate_digest_for_member.py` → `digest/agent.py:236` `generate_digest`)

1. Resolve `org_id` + `project_id`, set RLS context.
2. **Load the member profile** (`_load_member_profile`): `role`,
   `owned_subsystems`, `topic_weights`, timezone. *This is the
   personalization input.*
3. **Load project snapshot**: `current_phase`, `phase_concerns[phase]`.
4. **Gather candidate content** (`digest/repository.py`):
   - `top_scored_items_for_member` — the member's top ~20 messages by
     **score** (joins `scores`+`messages`+`message_tags`).
   - `open_cards_for_member_subsystems` — open cards whose
     `affected_subsystems` overlap the member's `owned_subsystems`
     (Postgres array overlap `&&`).
   - `list_recent_for_member` — last 3 digests, for novelty/continuity.
5. **Render the prompt** (`digest/prompts/system.txt` +
   `user.txt.j2`) and call **Sonnet** (tier = digest, temp 0.3) for a
   strict `DigestDraft` (`content_md` + which card/message ids it
   cited, bucketed into sections).
6. **Hallucination guard** (`_filter_cited_ids`): drop any cited id the
   model invented that wasn't in the candidate set. The model can only
   cite what we fed it.
7. **Fallback**: if the LLM errors, build a deterministic digest from
   the top scored items (top 8 / next 8 / next 8 → priority / watch-out
   / FYI). The product never shows an empty digest.
8. **Upsert** on `(project_member_id, day_index)` and **publish
   `digest_ready`** to the project channel.

**Key idea to articulate in an interview:** the LLM does *wording and
grouping*, not *ranking*. Ranking is deterministic code (the scorer).
That keeps the personalization explainable and testable, and keeps the
LLM from being able to smuggle in content the member shouldn't see.

---

## 5. Flow C — personalization (the scoring engine)

Scoring is **pure, deterministic Python** (`scoring/engine.py:54`
`score`) — no LLM. It runs once per member per message inside
`score_message_for_members` and writes the `scores` table.

Six weighted factors (`scoring/weights.py`, weights sum to 1.0):

| Factor | Weight | Meaning |
|---|---|---|
| `role_match` | 0.30 | member's role is in the message's `affected_roles` |
| `subsystem_match` | 0.25 | overlap between `owned_subsystems` and message `entities` |
| `urgency_boost` | 0.20 | critical=1.0 / high=0.6 / normal=0.3 / low=0 |
| `phase_concern_match` | 0.10 | message topic is a concern for the current project phase |
| `topic_weight` | 0.10 | **feedback-driven** per-member lever, clamped [-1, 1] |
| `cross_functional` | 0.05 | author is a *different* role but touches my subsystem |

`total = clamp(Σ weight·factor, 0, 1)`, stored with a `reasons`
breakdown (so a digest item can explain *why it matters to you*).
Indexed `(project_member_id, score DESC)` so the digest query is a
cheap top-N.

Because the score is computed **per member**, the same message lands
high for the chassis owner and near-zero for QA — that is the entire
personalization story, and it is inspectable row-by-row in the DB.

---

## 6. The feedback loop (adaptation over time)

1. User clicks 👍/👎 on a card → `POST /api/v1/cards/{id}/feedback`
   (`api/routes/cards.py:59`).
2. It atomically bumps `org_memberships.topic_weights[topic]` by
   ±1.0 (`_bump_membership_topic_weight:102`, a single JSONB `||`
   update).
3. The next time any message of that topic is scored, the
   `topic_weight` factor (weight 0.10) shifts, moving the item up or
   down the member's ranking — which changes what the *next* digest
   surfaces.

So "adapts as focus changes over time" is real and mechanical: feedback
→ topic weight → score → digest ordering. No retraining, no black box.

---

## 7. Eve — proactive cross-subsystem insights

`jobs/tasks/eve_insight.py` → `eve/agent.py` (`run_eve`). A tool-using
Sonnet agent with read tools (`search_messages`, `search_documents`,
…) and an `emit_insight` tool, run for up to ~8 turns. It hunts for a
high-impact change or a **spec-vs-chatter conflict** and emits a
structured insight with grounded sources.

Two layers of duplicate suppression (because an agent left alone will
re-report the same issue):

- **Prompt-level:** the last 8 insights are injected into the goal with
  "do NOT repeat these."
- **Embedding gate:** the new insight's title+summary is embedded
  (Voyage) and compared by cosine to recent ones; if
  `max_sim ≥ 0.82` it's rejected as a near-duplicate
  (`eve_insight.py:27,125`).

> **RLS subtlety here:** `run_eve` only reads, but its transaction is
> rolled back before the insert. `SET LOCAL app.current_org_id` is
> **transaction-scoped**, so the rollback drops it — the code
> re-applies `set_org_context` before the RLS-checked INSERT
> (`eve_insight.py:133`). A good example of RLS being enforced by the
> DB, not trusted to the app.

---

## 8. Multi-tenancy & RLS (the security spine)

- Every tenant-scoped table has `org_id`. Policies compare it to
  `current_setting('app.current_org_id', true)` and **fail closed** if
  unset.
- The app connects as a restricted role (`app_rw`) that cannot bypass
  RLS; migrations run as a privileged role.
- Context is set with `SET LOCAL` inside each request/worker
  transaction (`tenancy/rls.py`), so it can never leak across
  connections in the pool.
- Net effect: even a missing `WHERE org_id = …` in application code
  cannot leak another tenant's rows — the database refuses.

**View-as / impersonation** rides on top: the frontend sets a
`view_as` cookie; `lib/api.ts` forwards it as the `X-Impersonate-User`
header; `auth/deps.py` resolves the *viewed* membership (admin only)
while keeping the real `org_id`. So an admin sees any member's digest
without ever leaving their org.

---

## 9. Realtime (SSE) — how the UI stays live

- Each worker task publishes to a Redis channel keyed by **project_id**:
  `events:{project_id}` (`realtime.py`).
- The browser opens one `EventSource` to
  `GET /api/v1/events?project_id=…` (`api/routes/events.py`), which
  subscribes to that channel and streams events
  (`message_tagged`, `card_created`, `digest_ready`,
  `insight_created`).
- The hook `hooks/use-events.ts` routes each event to the right cache
  invalidation / refresh.

Two bugs fixed in this area (both worth knowing as "why it didn't work"
stories):

1. **Channel mismatch.** Three tasks were publishing to
   `events:{org_id}` while the client subscribes on
   `events:{project_id}` (`org_id ≠ project_id`). Every completion
   event was dropped. Fixed so all tasks publish on the project
   channel.
2. **SSE crash loop.** `_stream` caught the builtin `TimeoutError` but
   not `redis.exceptions.TimeoutError` (a different class); an idle
   socket read crashed the stream, and the browser reconnected every
   ~8s. Fixed by catching both as a keepalive.

---

## 10. "How does the user know the digest regenerated?" (the UX answer)

This is subtle and worth understanding precisely:

- The digest is **server-rendered** — `app/(app)/dashboard/page.tsx`
  fetches it once and passes it as props. There is **no client
  `useQuery(["digest"])`**, so invalidating that key does nothing on
  its own.
- Regenerate is **async**: the click returns 202 in milliseconds, but
  the worker needs ~20s (a Sonnet call). So there is a real gap between
  "clicked" and "new digest exists."

How it's wired now:

1. Click → a small Zustand store (`stores/regen.ts`) flips `pending`,
   so the button shows a spinner + **"Regenerating…"** and disables
   (with a 45s safety timeout so it can't get stuck).
2. The worker finishes (~20s) and publishes `digest_ready` on the
   project channel.
3. `use-events.ts` receives it → clears the pending flag **and calls
   `router.refresh()`**, which re-runs the server component fetch so
   the freshly-generated digest renders. The button returns to
   "Regenerate."

So the user gets: immediate "Regenerating…" feedback, then the digest
visibly updates itself ~20s later with no manual reload.

---

## 11. Tech stack (the "why")

- **FastAPI + async SQLAlchemy + asyncpg** — all I/O is async; HTTP
  handlers never block on LLM/DB.
- **Celery + Redis + Beat** — durable, replayable background work and
  sub-minute cron for the digest scan. Tasks are idempotent (unique
  constraints + upserts) so retries are safe.
- **Postgres 17 + pgvector** — one store for relational data *and*
  embeddings (RAG retrieval, Eve dedup). RLS for tenancy.
- **Anthropic tiering** — Haiku for high-volume tagging (cheap, fast),
  Sonnet for digest/cards/Eve (quality). All calls go through one
  client wrapper with retries + token logging.
- **Voyage `voyage-3-lite` (512-dim)** — embeddings for retrieval and
  semantic dedup.
- **Next.js App Router** — server components fetch with the user's JWT
  via a proxy route; client components only where interactivity demands
  it; TanStack Query for client server-state, Zustand sparingly.

---

## 12. Likely interview questions (and the crisp answer)

- **"Why is ranking not done by the LLM?"** Determinism,
  explainability, testability, and safety. The scorer is pure code with
  a per-factor breakdown; the LLM only writes prose over content we
  already chose. Personalization is inspectable row-by-row.
- **"How do you prevent one tenant seeing another's data?"** Postgres
  RLS, fail-closed, enforced by a restricted DB role — not by
  application `WHERE` clauses. Context is `SET LOCAL` per transaction.
- **"What happens if Slack redelivers an event?"** Nothing — dedup on
  `(source, external_id)` at the `raw_events` door; messages, tags, and
  scores all upsert. The whole pipeline is replay-safe.
- **"What if the LLM is down when a digest is due?"** Deterministic
  fallback digest from the top scored items. Never empty.
- **"How does it adapt to a user over time?"** Feedback bumps a JSONB
  `topic_weights` lever that feeds the scorer; the next digest reorders
  accordingly. No retraining.
- **"Why Celery and not background tasks in the request?"** Webhooks
  must return in milliseconds (Slack retries slow responses); LLM work
  takes seconds. Decoupling also gives retries, scheduling, and
  horizontal worker scaling.
- **"What's the weakest part / what's next?"** Single-project per org
  today; multi-project needs a channel→project mapping +
  `project_members`. Backfill is full-window (no incremental cursor).
  Eve's `list_recent_insights` dedup is O(recent) and won't scale to
  thousands of insights without an ANN index.

---

## 13. File map (where to look)

| Concern | Entry point |
|---|---|
| Slack webhook | `api/routes/webhooks.py`, `connectors/slack/events.py` |
| Routing/tagging | `jobs/tasks/route_message.py`, `routing/router_agent.py` |
| Card extraction | `jobs/tasks/build_card.py`, `cards/builder.py` |
| Scoring | `scoring/engine.py`, `scoring/weights.py`, `jobs/tasks/score_message.py` |
| Digest | `jobs/tasks/generate_digest_for_member.py`, `digest/agent.py`, `digest/scheduler.py` |
| Feedback | `api/routes/cards.py` (`post_card_feedback`) |
| Eve | `jobs/tasks/eve_insight.py`, `eve/agent.py` |
| Tenancy / RLS | `tenancy/rls.py`, `auth/deps.py` |
| Realtime | `realtime.py`, `api/routes/events.py`, `apps/web/hooks/use-events.ts` |
| Scheduling | `jobs/celery_app.py` (Beat), `jobs/celery_tasks.py` |
