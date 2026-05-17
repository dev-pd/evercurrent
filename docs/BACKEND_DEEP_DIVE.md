# Backend deep dive — distributed pipeline, phase-aware retrieval

This doc answers the backend architecture questions raised after the
prototype was demoed. It complements `ARCHITECTURE.md` (which sketches
boundaries) and `PRODUCTION_ROADMAP.md` (which sketches scale-out).

## 1. Where work happens — the distributed queue

```
                ┌──────────────┐
   HTTP client ─▶│   FastAPI    │  request path: fast, never blocks on LLM
                │   (uvicorn)  │
                └──────┬───────┘
                       │ enqueue_job(…)
                       ▼
                ┌──────────────┐
                │    Redis     │  Arq queue + heartbeat KV
                └──────┬───────┘
                       │ pop
                       ▼
                ┌──────────────┐
                │  Arq worker  │  LLM + DB heavy lifting
                │  (1 .. N)    │  scales horizontally
                └──────┬───────┘
                       │ writes
                       ▼
                ┌──────────────┐
                │  Postgres 17 │  pgvector, JSONB, ARRAY
                └──────────────┘
```

- API process never calls an LLM in the request path. It validates
  input, persists scalar state (phase change, feedback), and pushes a
  job onto Arq when the work is non-trivial.
- Worker is its own Docker service (`worker` in compose). Today one
  replica; scale by setting `--scale worker=N` or by changing the
  compose replicas count. State is partitioned by job id so two
  workers grabbing the same job is impossible.

### Per-user rerank lives in the queue

`POST /digests/{user_id}/regenerate?day=N&project_id=P` enqueues the
function `regenerate_user_digest` with a **deterministic** job id:

```
regen:{project_id}:{user_id}:{day}:{phase}
```

Arq deduplicates on job id, so a frenetic user clicking Regenerate
five times queues one job, not five. The endpoint returns 202 with the
job id; the frontend polls `GET /jobs/{job_id}` and renders a spinner
until status flips to `complete`.

Why deterministic ids matter at scale: in production we expect 10k+
active users. Without dedup, a flapping web client could pump duplicate
work into the queue and starve real load. With dedup, the queue depth is
bounded by `users × days × phases` cells, not by click frequency.

### Tasks registered today

| Task                            | Triggered by                          | Tier   |
|---------------------------------|---------------------------------------|--------|
| `heartbeat`                     | smoke / liveness                      | —      |
| `enrich_day`                    | seed + manual                         | Haiku  |
| `generate_all_digests`          | seed + manual                         | Sonnet |
| `extract_decisions_for_day`     | seed + manual                         | Sonnet |
| `ingest_document`               | doc upload                            | Voyage |
| `regenerate_user_digest`        | feedback / phase-switch (when needed) | Sonnet |
| `advance_day`                   | not in UI now; reserved for ops       | mixed  |

Each task is a thin orchestrator. Business logic lives in
`evercurrent.<module>.*` and is import-time independent of Arq, so the
same code runs in tests + evals without a worker.

## 2. Phase-aware retrieval

Two distinct phase tracks:

### Per-(user, day, phase) digests

`digests` is now keyed `UNIQUE (user_id, day, phase)`. The
`precompute_all_digests` step writes every cell at seed time —
8 users × 5 days × 6 phases = 240 Sonnet calls. After that, phase
switching is **purely a metadata flip** (`POST /projects/{id}/phase`)
plus a query-key change on the client; the digest endpoint reads the
matching precomputed row. No LLM call in the hot path.

When a user clicks thumbs up/down, we *only* bump
`user.topic_weights[topic]`. The next manual Regenerate, or the next
scheduled precompute sweep, picks up the new weight. UI stays snappy.

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

`search_documents(..., phase=X)` filters with:

```sql
(cardinality(d.phases) = 0 OR :phase = ANY(d.phases))
```

Documents with empty `phases` are treated as universal (today only
"other" kind hits that). The agent runner uses the active project phase
when calling `search_documents`, so retrieval no longer surfaces a
drop-test report when the project is in `design`.

The Documents page exposes this directly: a phase chip per doc, an
"active phase" highlight, and a toggle to show only docs that match
the current phase.

## 3. Idempotency + back-pressure

- DB writes are all upserts (`ON CONFLICT DO UPDATE`) keyed on natural
  unique tuples: `(user_id, day, phase)` for digests, `(message_id)` for
  tags, `(project_id, name)` for projects/users/channels.
- Per-day digests survive worker restarts. If a worker dies mid-batch,
  re-running the task replaces the affected cells but never duplicates
  them.
- LLM client retries on `APIConnectionError`, `APITimeoutError`,
  `RateLimitError`, and 5xx `APIStatusError`. Exponential backoff, 4
  attempts, capped at 8s. Anthropic 4xx surfaces immediately so we don't
  loop on bad input.
- Voyage embedder mirrors the same retry policy.

## 4. Boundaries that let this scale

- **Adapters at the edge.** `LLMProvider`, `EmbeddingProvider`,
  `Tagger`, `DigestGenerator` are Protocols. Swapping Anthropic for
  a self-hosted model, or Voyage for OpenAI, is a one-file change.
- **Repositories return domain models.** Nothing above the `db/` layer
  imports SQLAlchemy. Refactoring storage (e.g. read replicas, sharding)
  is contained.
- **Scoring is pure Python.** No DB, no LLM. Trivially parallelisable
  across users on the worker — eval scenarios in
  `apps/api/tests/evals/test_scoring_eval.py` exercise it deterministically.
- **Heuristic fallbacks.** Set `ANTHROPIC_API_KEY=` empty and the tagger
  + digest generator fall back to deterministic rule-based output. CI,
  evals, and demos all run without keys.

## 5. What this enables in product

- Tenant scale: each project gets one row of `phase_concerns` and one
  set of precomputed digests; the worker fans out per project. No
  cross-project locking.
- Real-time UI: phase swap is a single Postgres write. Feedback is a
  single INSERT + JSONB update. Both are <10ms.
- Predictable LLM spend: at 240 cells × $0.005/Sonnet call, one project
  costs ~$1.20 to fully precompute. With prompt caching on the system
  prompt + tool spec, that drops by ~70% in production.
- Audit + replay: every Arq job + its parameters + result are recorded.
  Re-running an old job id reproduces the exact same digest as long as
  the seed message corpus hasn't moved.

## 6. What's intentionally not done yet

- **Live notification on job completion.** Today the UI polls
  `/jobs/{id}`. WebSocket or SSE would replace the poll loop;
  infrastructure is there (the agent route already streams SSE).
- **RBAC + multi-tenant scoping.** Repositories take a `project_id` but
  we don't enforce an org boundary. Postgres RLS keyed on `org_id`
  + a request-scoped context is the obvious next step.
- **Cost dashboard.** Every LLM call logs `model`, `input_tokens`,
  `output_tokens`, `latency_ms` via structlog. A nightly job rolling
  these into Postgres is one more Arq task.
- **Continuous embedding.** Documents re-embed on demand via
  `ingest_document`. A change-data-capture path (Postgres LISTEN or a
  trigger) would auto-enqueue ingest on every `documents` UPDATE.
