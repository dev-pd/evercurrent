# apps/api — EverCurrent backend

FastAPI on Python 3.13 + uv. Celery worker + beat for async work.
SQLAlchemy 2.0 async over Postgres 17 + pgvector. Redis 8 as broker
and SSE pub/sub bus.

## Run

Everything is docker-only from the repo root. See top-level README.

```bash
# from repo root
make up                       # api + worker + beat + postgres + redis + web + nginx
make migrate                  # apply Alembic schema
make seed                     # project + 8 users + channels + 42 messages + 5 docs
make test                     # health + ready unit tests
make eval                     # scoring + determinism suite
```

Direct docker invocations:

```bash
docker compose exec api uvicorn evercurrent.main:app --reload    # dev API
docker compose exec api alembic upgrade head                     # migrate
docker compose logs -f worker                                    # watch tasks
docker compose logs -f beat                                      # watch cron
```

## Layout

```
apps/api/
├── pyproject.toml              uv-managed dependencies
├── alembic.ini, alembic/       schema migrations (incl. pgvector + dates)
├── seed_data/                  committed project/users/channels JSON,
│                               seed messages (days 1-5), markdown docs
├── src/evercurrent/
│   ├── config.py               pydantic-settings (DB, Redis, LLM keys)
│   ├── main.py                 FastAPI app factory + lifespan + middleware
│   ├── domain/                 pure Pydantic models (strict mode)
│   ├── db/
│   │   ├── models.py           SQLAlchemy 2.0 async ORM
│   │   ├── session.py          engine + session factory
│   │   └── repositories/       domain-model-returning data access
│   ├── ingestion/              seeder + (future) Slack adapter slot
│   ├── enrichment/             Haiku tagger + heuristic fallback
│   ├── scoring/                pure-Python ranker + synonyms
│   ├── digest/                 Sonnet generator + heuristic fallback
│   ├── decisions/              Sonnet decision extractor
│   ├── rag/                    Voyage embedder + chunker + retriever
│   ├── agent/                  6-tool runner + SSE relay (backend-only now)
│   ├── jobs/
│   │   ├── celery_app.py       Celery + Beat schedule
│   │   ├── celery_tasks.py     sync wrappers calling asyncio.run(...)
│   │   └── tasks/              async impls (refresh_today, synthesize, …)
│   ├── realtime.py             Redis pub/sub publisher for SSE events
│   ├── llm/                    Anthropic client wrapper + model tiering
│   └── api/
│       ├── routes/             projects, users, digests, feedback,
│       │                       decisions, documents, today, events, jobs
│       ├── schemas.py          wire-level Pydantic shapes
│       ├── deps.py             FastAPI dependency factories
│       └── middleware.py       request-id + structlog binding
└── tests/
    ├── evals/                  scoring scenarios + determinism (`make eval`)
    └── unit/                   health + ready only (test policy in AGENTS.md)
```

## Tooling

- `uv` for env + deps. No pip / poetry / requirements.txt.
- `ruff` for lint + format. `ty` for type check.
- `pytest` for the two unit tests (`health`, `ready`) plus the eval
  harness — `make test` and `make eval` from repo root.
- Celery + Beat for the queue; Redis is broker + result backend.
