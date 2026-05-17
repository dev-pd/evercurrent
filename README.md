# EverCurrent

An agentic AI layer for hardware engineering teams. Personalizes information by
role, project phase, and behavior. Tracks cross-functional dependencies.
Extracts structured decisions from team conversations. Answers questions by
reasoning across team docs and chatter.

> Status: phase 0 (scaffolding). Not yet runnable end-to-end. See
> `EVERCURRENT_BUILD_DOC.md` for the full build plan.

## Quickstart

```bash
# 1. Prereqs: Docker Desktop, plus (for local non-container dev) uv, pnpm, Node 25+
# 2. Copy env template and fill in your API keys
cp .env.example .env
#    edit .env: ANTHROPIC_API_KEY=..., VOYAGE_API_KEY=...
# 3. Bring up the full stack (postgres + redis + api + worker + web + nginx)
docker compose up --build
# 4. Open the unified entry point
#       http://localhost           # nginx routes / -> web, /api/* -> api
#       http://localhost:3000      # direct Next.js dev port
#       http://localhost:8000/health  # direct API healthcheck
```

`docker compose down` cleans up. `docker compose down -v` also removes the
Postgres and Redis volumes.

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
