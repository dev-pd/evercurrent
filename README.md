# EverCurrent

An agentic AI layer for hardware engineering teams. Personalizes information by
role, project phase, and behavior. Tracks cross-functional dependencies.
Extracts structured decisions from team conversations. Answers questions by
reasoning across team docs and chatter.

> Status: phase 0 (scaffolding). Not yet runnable end-to-end. See
> `EVERCURRENT_BUILD_DOC.md` for the full build plan.

## Quickstart

Everything runs in docker. Only Docker Desktop is required on the host.

```bash
# 1. Copy env template and fill in your API keys
cp .env.example .env
#    edit .env: ANTHROPIC_API_KEY=..., VOYAGE_API_KEY=...
# 2. Build + bring up the full stack
make up                    # = docker compose up -d --build
# 3. Apply DB migrations (creates schema + pgvector extension)
make migrate
# 4. Open the unified entry point
#       http://localhost:8080            # nginx routes / -> web, /api/* -> api
#       http://localhost:8080/api/health # API healthcheck through nginx
```

Only `nginx` is exposed on the host (port `8080`). `postgres`, `redis`, `api`,
`worker`, and `web` are internal to the docker network. To reach them, use
`docker compose exec <service> ...` (or the `make` helpers below).

Useful one-liners:

- `make ps` — container status
- `make logs` — tail all service logs
- `make psql` — psql shell into postgres
- `make shell-bash` — bash shell in the api container
- `make lint` — ruff + ty + eslint + prettier + tsc, all inside docker
- `make test` — pytest health/ready unit tests inside docker
- `make down` — stop stack (preserves volumes)
- `make down-v` — stop stack and wipe volumes

## Layout

- `apps/api/` — FastAPI backend (Python 3.13, uv)
- `apps/web/` — Next.js 16.2 frontend (TypeScript, App Router, Tailwind v4)
- `docs/` — Architecture, production roadmap, eval baseline, learning notes
- `EVERCURRENT_BUILD_DOC.md` — Authoritative build plan (phases + subphases)
- `AGENTS.md` — Coding standards (single source of truth)
- `CLAUDE.md` — Claude Code session pointer (imports `AGENTS.md`)

## Documentation

Deeper docs live in `docs/`:

- `ARCHITECTURE.md` — design decisions, layer boundaries, data flow
- `PRODUCTION_ROADMAP.md` — scale-out story
- `EVAL_BASELINE.md` — eval harness baseline numbers
- `LEARNING_NOTES.md` — engineer's log

## License

MIT. See `LICENSE`.
