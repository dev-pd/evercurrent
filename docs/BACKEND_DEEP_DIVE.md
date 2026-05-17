# Backend deep dive — distributed pipeline, SSE, phase-aware retrieval

The frontend is intentionally thin. Every interesting decision is in
the backend. This doc walks the queue, the pub/sub fanout, the cached
phase variants, and the cron-driven live stream.

## 1. Where work happens — Celery + Redis

```
                ┌──────────────┐
   HTTP client ─▶│   FastAPI    │  request path: fast, never blocks on LLM
                │   (uvicorn)  │
                └──────┬───────┘
                       │ task.delay(...)
                       ▼
                ┌──────────────┐
                │    Redis     │  Celery broker + result backend + pub/sub
                └──────┬───────┘
                       │ prefetch
                       ▼
                ┌──────────────┐
                │ Celery worker│  asyncio.run(<async impl>) in a fork pool
                │  (1..N)      │  --concurrency=4 per replica
                └──────┬───────┘
                       │ writes
                       ▼
                ┌──────────────┐
                │  Postgres 17 │  pgvector, JSONB, ARRAY
                └──────────────┘

       ┌──────────────┐
       │ Celery beat  │  cron schedules: refresh_today @ 30s,
       │              │  synthesize_today_message @ 60s
       └──────┬───────┘
              ▼
       (enqueues onto the same Redis broker as the API)
```

- API never calls an LLM in the request path. It validates input,
  persists scalar state (phase change, feedback), and pushes a task
  onto Celery when work is non-trivial.
- Worker is its own Docker service (`worker` in compose). Scale via
  `--scale worker=N` or by raising `--concurrency`.
- Beat is a separate service (`beat`) with its own schedule file
  (`/tmp/celerybeat-schedule`) so the non-root user can persist it.

### Per-user re-rank flow

`POST /digests/{user_id}/regenerate?day=N&project_id=P` calls
`regenerate_user_digest.delay(...)` and returns 202 with a fresh
Celery task id. The frontend polls `GET /jobs/{task_id}` until the
status flips out of `pending` / `started` / `retry` (every click is
a new task id — Celery does not dedup against completed results).

When the task finishes it publishes a `digest.updated` event onto
`events:{project_id}` and the SSE relay pushes it to every connected
dashboard. The browser invalidates `["digest", ...]` and refetches.

### Tasks registered today

| Task                              | Trigger                            | Tier   |
|-----------------------------------|------------------------------------|--------|
| `heartbeat`                       | smoke / liveness                   | —      |
| `enrich_day`                      | seed + cron                        | Haiku  |
| `generate_all_digests`            | seed + manual                      | Sonnet |
| `extract_decisions_for_day`       | seed + cron                        | Sonnet |
| `ingest_document`                 | doc upload                         | Voyage |
| `regenerate_user_digest`          | feedback / phase cold-start        | Sonnet |
| `refresh_today`                   | beat cron / 30s                    | mixed  |
| `synthesize_today_message`        | beat cron / 60s                    | Sonnet |
| `advance_day`                     | reserved for ops                   | mixed  |

Each Celery task is a thin sync wrapper that calls
`asyncio.run(<async impl>)`. Async business logic stays where it
lives in `evercurrent.<module>.*`; the worker runtime doesn't leak
into domain code.

## 2. Realtime — SSE over Redis pub/sub

No periodic polling. The browser opens one EventSource per dashboard
mount; the server pushes when something actually changes.

```
Celery task body              FastAPI /events route               Browser
─────────────────             ─────────────────────              ────────
write digest row             redis.asyncio.subscribe              EventSource
publish_event(                events:{project_id})                useEvents()
  project_id, type,            │                                  │
  payload)                     │ async for message:                │
  │                            │   yield "event: update\n"        │
  │                            │         "data: <json>\n\n"       │
  ▼                            │                                  │
redis.publish(                 ▼                                  ▼
  "events:{id}", body) ───────► relay                              invalidate
                                                                  TanStack Query
```

Heartbeat: `: keepalive\n\n` every 15s so proxies (nginx, ALB) don't
kill idle connections. nginx already disables proxy_buffering for
`/api/events` and `/api/agent/`.

Event vocabulary:
- `digest.updated {day, phase, user_id?}`
- `message.synthesized {count}`
- `phase.changed {phase}`
- `decisions.updated`

## 3. Phase-aware retrieval — two layers

### Per-(user, day, phase) digest cache

`digests` is `UNIQUE (user_id, day, phase)`. Seed precomputes every
cell via `make precompute-digests` — 8 users × N days × 6 phases.
After that, phase switch = a single Postgres write + one cached read.
No LLM call in the hot path.

A cold cell (phase variant never computed) triggers a queued
regenerate from the dashboard and shows a "Showing cached X — Y
variant building" banner while the task runs.

### Per-document phase scope

`documents.phases TEXT[]` lists the project phases each doc is
authoritative for:

| Document kind          | Phases                            |
|------------------------|-----------------------------------|
| PRD                    | concept, design, EVT, DVT, PVT, MP|
| BOM                    | DVT, PVT, MP                      |
| ECO log                | EVT, DVT, PVT                     |
| Test report (thermal)  | DVT, PVT                          |
| Test report (drop)     | DVT, PVT                          |

`rag.retriever.search_documents(..., phase=X)` filters with
`cardinality(d.phases) = 0 OR :phase = ANY(d.phases)`. The agent's
`search_documents` tool passes the active phase, so retrieval stops
surfacing test reports during the design phase.

## 4. "Today" = calendar today

`project.start_date` (DATE) anchors the ordinal-day axis. Day N maps
to `start_date + (N-1)`. `Project.today_day` computes today's ordinal
from UTC wall clock; `refresh_today` rolls `current_day` forward
every tick if reality has advanced past it.

`/today` returns `live_day, live_date, start_date, phase,
phase_concerns, message_count, last_message_at,
last_digest_generated_at`. The UI renders calendar dates everywhere;
the int day is an implementation detail.

The Slack stream is simulated by `synthesize_today_message` (Sonnet
generates 2 phase-scoped messages per tick). In production this task
is replaced by a Slack Events webhook handler that enqueues
`enrich + nudge refresh` per inbound message. The 30s `refresh_today`
cron stays as a backstop so debounced batches always flush.

## 5. Idempotency + back-pressure

- DB writes are all upserts (`ON CONFLICT DO UPDATE`) on natural
  unique tuples: `(user_id, day, phase)` for digests,
  `(message_id)` for tags, `(project_id, name)` for
  projects/users/channels.
- Per-day digests survive worker restarts. Re-running a task replaces
  affected cells, never duplicates.
- LLM client retries on `APIConnectionError`, `APITimeoutError`,
  `RateLimitError`, 5xx `APIStatusError`. Exponential backoff,
  4 attempts, capped at 8s. 4xx surfaces immediately.
- Voyage embedder mirrors the retry policy.
- Celery defaults: `task_acks_late=True`,
  `worker_prefetch_multiplier=1`, `task_default_retry_delay=5`,
  `task_default_max_retries=2`.

## 6. Boundaries that let this scale

- **Adapters at the edge.** `LLMProvider`, `EmbeddingProvider`,
  `Tagger`, `DigestGenerator` are Protocols. Swapping Anthropic /
  Voyage is a one-file change.
- **Repositories return domain models.** No SQLAlchemy above
  `db/`. Refactoring storage is contained.
- **Scoring is pure Python.** No DB, no LLM. Eval scenarios in
  `tests/evals/test_scoring_eval.py` exercise it deterministically.
- **Heuristic fallbacks.** With `ANTHROPIC_API_KEY` empty, the tagger
  + digest generator emit deterministic markdown. CI runs without
  keys.

## 7. What this enables in product

- Tenant scale: each project has one `phase_concerns` row + one
  precomputed digest grid; the worker fans out per project.
- Real-time UI: phase swap = single Postgres write. Feedback = one
  INSERT + JSONB update. Both <10ms. Digest refresh ≤30s (cron) or
  on push (SSE).
- Predictable LLM spend: 8 users × ~7 days × 6 phases ≈ 336 cells at
  ~$0.005/Sonnet call ≈ $1.70 to fully precompute one project.
- Audit + replay: every Celery task records args + result. Re-running
  an old task id reproduces the same digest if the seed corpus
  hasn't moved.

## 8. Deferred work

- **Celery → Temporal** when workflow durability + signals beat
  Celery's chain/canvas semantics.
- **WebSocket** replacing SSE if the UI grows bidirectional needs
  (live cursor presence, multi-user editing).
- **RBAC + multi-tenant scoping.** Repos take `project_id`; Postgres
  RLS on `org_id` plus a request-scoped context is the next step.
- **Cost dashboard.** Every LLM call already logs `model`,
  `input_tokens`, `output_tokens`, `latency_ms` via structlog. A
  nightly Celery task aggregating these is small.
- **Continuous embedding via CDC.** Postgres `LISTEN` on documents
  UPDATE triggers `ingest_document` instead of manual `make
  ingest-docs`.
