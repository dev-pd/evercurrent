# EverCurrent

An agentic AI layer for hardware engineering teams. Personalizes information by
role, project phase, and behavior. Tracks cross-functional dependencies.
Extracts structured decisions from team conversations. Answers questions by
reasoning across team docs and chatter.

> Status: phase 0 (scaffolding). Not yet runnable end-to-end. See
> `EVERCURRENT_BUILD_DOC.md` for the full build plan.

## Quickstart

```bash
# 1. Prereqs: Docker, uv, pnpm, Node 25+
# 2. Copy env template (added in Phase 0.2)
cp .env.example .env  # fill ANTHROPIC_API_KEY and VOYAGE_API_KEY
# 3. Run the stack (added in Phase 0.2)
make up
# 4. Open http://localhost:3000
```

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
