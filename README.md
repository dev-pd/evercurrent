# EverCurrent

> An agentic AI layer for hardware engineering teams. Personalises Slack-style
> conversations by role + project phase + cross-functional dependencies.
> Extracts structured decisions from chatter. Answers questions across team
> docs and messages with a 6-tool reasoning agent.

## Quickstart (docker-only)

```bash
cp .env.example .env          # fill ANTHROPIC_API_KEY + VOYAGE_API_KEY
make up                       # postgres + redis + api + worker + web + nginx
make migrate                  # 10 tables, pgvector + pgcrypto extensions
make seed                     # project + 8 users + 5 channels + 42 messages + 5 docs
open http://localhost:8080
```

Stop with `make down`. Reset with `make down-v` (wipes volumes).

| Route                          | Notes                                   |
|--------------------------------|-----------------------------------------|
| `http://localhost:8080`        | Dashboard via nginx                     |
| `http://localhost:8080/api/health` | Liveness probe                      |
| `http://localhost:8080/api/ready`  | DB-reachable readiness check         |

Only nginx is exposed on the host — everything else is internal to the
docker network. See `docs/ARCHITECTURE.md` for the diagram.

## What's inside

- **Personalised digest** — `scoring/engine.py` ranks messages per user
  by role, owned subsystems/parts, urgency, phase concerns, and learned
  feedback weights. The Sonnet generator turns the top 8 into a
  one-shot markdown briefing with `[msg_<id>]` citations.
- **Cross-functional dependency match** — `scoring/dependencies.py`
  fuzzy-matches owned subsystems (e.g. "chassis") against tagged
  entities (e.g. "BRK-A1", "AL-6063-T5") via an explicit synonym map.
- **Decision extraction** — `decisions/extractor.py` runs Sonnet over
  a day's messages, validates strictly with Pydantic, downgrades
  borderline outputs to `proposed` via a confidence cutoff.
- **RAG** — pgvector HNSW + cosine, voyage-3-lite at 512 dims, markdown
  chunker that preserves section paths.
- **Agent** — 6 tools (search_messages, get_thread_context,
  get_user_context, get_project_state, search_documents,
  query_decisions), Sonnet tool-use loop, SSE streaming to the
  Next.js chat panel.
- **Heuristic fallbacks** — without API keys the tagger and digest
  generator emit deterministic markdown so the pipeline runs end-to-end
  for CI and demos.

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
│   │   │   ├── agent/      6-tool runner + SSE serialiser
│   │   │   ├── jobs/       Arq worker + tasks
│   │   │   ├── api/        FastAPI routes + schemas + deps
│   │   │   └── llm/        Anthropic client wrapper + model tiering
│   │   ├── tests/{evals,unit}
│   │   ├── alembic/versions
│   │   └── seed_data/      committed JSON + markdown
│   └── web/                Next.js 16.2 + React 19 + Tailwind v4
│       ├── app/            App Router pages
│       ├── components/     ui/ · layout/ · digest/ · chat/ · simulation/
│       ├── hooks/          use-agent (SSE stream)
│       ├── lib/            api client · stream parser · types · utils
│       └── stores/         zustand impersonation store
├── docs/
│   ├── ARCHITECTURE.md     diagrams + layer boundaries + design notes
│   ├── PRODUCTION_ROADMAP.md  scale-out story
│   ├── EVAL_BASELINE.md    eval numbers + investigation triggers
│   ├── DEMO_SCRIPT.md      5-minute walkthrough
│   ├── LEARNING_NOTES.md   engineer's log
│   └── CONTRIBUTING.md     conventions
├── nginx/nginx.conf
├── docker-compose.yml
├── Makefile
├── EVERCURRENT_BUILD_DOC.md  authoritative build plan
├── AGENTS.md                 coding standards + test policy
└── CLAUDE.md                 Claude Code entrypoint (imports AGENTS.md)
```

## Eval results

`make eval` runs scoring + determinism scenarios. Current baseline:

| Suite                | Result        |
|----------------------|---------------|
| Scoring scenarios    | **6 / 6**     |
| Determinism (10/100) | **stable**    |
| Decisions extracted  | 23 across 5 days |

See `docs/EVAL_BASELINE.md` for the full table + investigation triggers.

## Three things to read first

1. `docs/ARCHITECTURE.md` — system + data flow + design decisions.
2. `docs/PRODUCTION_ROADMAP.md` — the production path: Slack adapter,
   multi-tenancy, compliance, observability, RAG evolution, AWS deploy.
3. `docs/DEMO_SCRIPT.md` — 5-minute walkthrough mirroring the demo
   video.

## License

MIT. See `LICENSE`.
