# EverCurrent

> An agentic AI layer for hardware engineering teams. Personalises a
> continuous stream of Slack-style updates by role, owned subsystems,
> and project phase. Re-ranks in real time as messages arrive. Extracts
> structured decisions. Backend-heavy by design — the UI is read-only,
> the queue does the work.

## Quickstart (docker-only)

```bash
cp .env.example .env          # fill ANTHROPIC_API_KEY + VOYAGE_API_KEY (optional)
make up                       # postgres + redis + api + worker + beat + web + nginx
make migrate                  # apply Alembic schema (incl. pgvector + pgcrypto)
make seed                     # project + 8 users + 5 channels + 42 seed messages + 5 docs
open http://localhost:8080
```

The Celery beat scheduler immediately rolls `current_day` to today's
calendar date, the worker starts synthesising fresh messages and
re-ranking digests on a 30s/60s cadence, and the dashboard receives
server-pushed SSE events for every change.

## Architecture (backend-heavy)

```
                         ┌─────────────────────────────┐
   Slack-like inbound ─▶ │  synthesize_today_message   │  Celery beat / 60s
                         │  (Sonnet writes 2 phase-    │  (production: Slack
                         │   scoped messages/tick)     │   webhook listener)
                         └────────────┬────────────────┘
                                      ▼
                         ┌─────────────────────────────┐
                         │  refresh_today (beat / 30s) │  enrich -> rank -> digest
                         │   - Haiku tags new msgs     │  -> extract decisions
                         │   - Sonnet rewrites digests │
                         │     for current_phase × all │
                         │     users                   │
                         │   - publishes               │
                         │     `digest.updated` to     │
                         │     Redis pub/sub           │
                         └────────────┬────────────────┘
                                      ▼
                         ┌─────────────────────────────┐
                         │  /events SSE relay          │  subscribes to
                         │   (FastAPI)                 │  events:{project_id}
                         └────────────┬────────────────┘
                                      ▼
                         ┌─────────────────────────────┐
                         │  Browser EventSource        │  invalidates
                         │   (useEvents hook)          │  TanStack Query
                         └─────────────────────────────┘
```

Every (user, day, phase) digest is precomputed and cached. Phase swap
on the UI = a single Postgres write + a query invalidation; no LLM
call in the request path. Per-user re-rank goes onto the Celery queue
with a fresh task id; UI polls `/jobs/{task_id}` only for that
specific click, ~10s.

See `docs/ARCHITECTURE.md` and `docs/BACKEND_DEEP_DIVE.md`.

## Layout

```
evercurrent/
├── apps/
│   ├── api/                FastAPI backend (Python 3.13 + uv)
│   │   ├── src/evercurrent/
│   │   │   ├── domain/     pure Pydantic models (no I/O)
│   │   │   ├── db/         SQLAlchemy 2.0 async ORM + repositories
│   │   │   ├── ingestion/  seeder + (future) Slack adapter slot
│   │   │   ├── enrichment/ Claude Haiku tagger + heuristic fallback
│   │   │   ├── scoring/    pure-Python ranker + weights + synonyms
│   │   │   ├── digest/     Claude Sonnet generator + heuristic fallback
│   │   │   ├── decisions/  Sonnet extractor with confidence cutoff
│   │   │   ├── rag/        Voyage embedder + markdown chunker + retriever
│   │   │   ├── agent/      6-tool runner (SSE chat endpoint, backend-only)
│   │   │   ├── jobs/       Celery app + tasks + beat schedule
│   │   │   ├── realtime.py Redis pub/sub publisher for SSE events
│   │   │   ├── api/        FastAPI routes + schemas + deps
│   │   │   └── llm/        Anthropic client wrapper + model tiering
│   │   ├── tests/{evals,unit}
│   │   ├── alembic/versions
│   │   └── seed_data/      committed JSON + markdown
│   └── web/                Next.js 16.2 + React 19 + Tailwind v4
│       ├── app/            App Router pages: /dashboard, /decisions, /docs
│       ├── components/     ui/ · layout/ · digest/ · simulation/
│       ├── hooks/          use-events (SSE subscription)
│       ├── lib/            api client · types · utils
│       └── stores/         zustand impersonation store
├── docs/
│   ├── ARCHITECTURE.md      diagrams + layer boundaries + design decisions
│   ├── BACKEND_DEEP_DIVE.md distributed queue + phase-aware retrieval
│   ├── PRODUCTION_ROADMAP.md scale-out story
│   ├── EVAL_BASELINE.md     eval numbers
│   ├── DEMO_SCRIPT.md       5-minute walkthrough
│   ├── LEARNING_NOTES.md    engineer's log
│   └── CONTRIBUTING.md      conventions
├── nginx/nginx.conf
├── docker-compose.yml       postgres · redis · api · worker · beat · web · nginx
├── Makefile
├── AGENTS.md                coding standards + test policy
└── CLAUDE.md                Claude Code entrypoint (imports AGENTS.md)
```

## Eval results

`make eval` runs scoring + determinism scenarios. Current baseline:

| Suite                | Result        |
|----------------------|---------------|
| Scoring scenarios    | **6 / 6**     |
| Determinism (10/100) | **stable**    |
| Decisions extracted  | ~20 / 5 days  |

See `docs/EVAL_BASELINE.md`.

## Three things to read first

1. `docs/BACKEND_DEEP_DIVE.md` — Celery queue, Redis pub/sub, SSE
   relay, per-(user, day, phase) digest cache.
2. `docs/ARCHITECTURE.md` — system + data flow + design decisions.
3. `docs/PRODUCTION_ROADMAP.md` — scale-out (Slack adapter,
   multi-tenancy, observability, compliance, AWS).

## License

MIT. See `LICENSE`.
