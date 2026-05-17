# apps/api — EverCurrent backend

FastAPI backend on Python 3.13 with uv.

## Run (Phase 0.1)

```bash
cd apps/api
uv sync
uv run fastapi dev src/evercurrent/main.py
```

Then `curl http://localhost:8000/health` should return `{"status":"ok"}`.

## Layout

```
apps/api/
├── pyproject.toml          dependency manifest (single source of truth)
├── src/evercurrent/        package root
│   ├── __init__.py
│   └── main.py             FastAPI app factory + /health (phase 0.1)
└── README.md
```

Module structure for later phases (domain, db, ingestion, enrichment,
scoring, digest, decisions, rag, agent, jobs, api, llm) is documented in
`AGENTS.md` §4 and `EVERCURRENT_BUILD_DOC.md` §3.

## Tooling

- `uv` for env + dependency management. No pip, poetry, or requirements.txt.
- `ruff` for lint + format. `ty` for type check. Configured in
  `pyproject.toml`.
- `pytest` for the two unit tests (health, ready) and eval harness.
