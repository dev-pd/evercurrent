# EverCurrent

> A multi-tenant agentic platform for hardware engineering teams.
> Connects to Slack + Google Drive + (roadmap) GitHub/Jira/Email.
> An autonomous Router agent classifies every inbound event, a Digest
> agent drafts a personalised morning briefing per engineer per day,
> and Knowledge Cards become the atomic unit of "what decisions /
> risks / open questions matter right now."

**Status:** v2 pivot — actively being built phase-by-phase per
`docs/phases/`.

## Pivot notice

The current codebase is mid-rewrite from a single-tenant digest
prototype (built ~3 weeks ago) to a multi-tenant agentic platform.
Architecture, data model, agent design, and UI all change.

- **What changed and why:** `docs/DECISIONS.md`
- **Build plan, phase by phase:** `docs/phases/README.md`
- **File-by-file migration (keep / rewrite / delete):**
  `docs/MIGRATION.md`
- **Old build doc (historical):** `EVERCURRENT_BUILD_DOC.md`

## Quickstart (after Phase 1 ships)

```bash
cp .env.example .env          # fill keys (see docs/DEV_SETUP.md)
make up                       # docker-compose: postgres + redis + api + worker + beat + web
make migrate                  # apply schema
make ngrok                    # expose port 8000 for Slack/Drive webhooks
open http://localhost:3000
```

Currently the repo is at Phase 0 baseline. Phase 1 lands the infra
(docker-compose, plugins, pre-commit, CI). Until then, the FE serves
a placeholder.

## Read order

1. **`docs/PRD.md`** — what we build, in plain English. Includes a
   day-in-the-life walkthrough and every screen mocked out.
2. **`docs/SYSTEM_DESIGN.md`** — data model, API surface, service
   layout, request lifecycle.
3. **`docs/AGENT_VS_WORKFLOW.md`** — how the agent fits, what it
   automates, where workflows handle the plumbing.
4. **`docs/DECISIONS.md`** — every architectural choice as an ADR
   with the "why."
5. **`docs/phases/README.md`** — the phase-by-phase build plan.
6. **`docs/TESTING_STRATEGY.md`** — TDD on deterministic code,
   eval harness on LLM code.

## Stack (locked)

### Backend

- Python 3.13 + uv
- FastAPI 0.136, Pydantic 2.12 strict, SQLAlchemy 2.0 async, Alembic
- Postgres 17 + pgvector 0.8 (HNSW)
- Celery 5.4 + Beat (Redis broker)
- Anthropic SDK (Claude Sonnet 4.6 + Haiku 4.5)
- Voyage AI `voyage-3-lite` (512 dims)
- FastMCP for the tool layer
- Auth0 for multi-tenant identity
- structlog, ruff, ty

### Frontend

- Node 25, pnpm 11
- Next.js 16.2 App Router, React 19, TypeScript 5 strict
- Tailwind v4, shadcn/ui, Lucide
- TanStack Query v5, Zustand (sparingly), Zod
- vitest + @testing-library/react + msw, Playwright

### Infra (local only for take-home)

- Docker + docker-compose
- ngrok for webhook URL during dev
- GitHub Actions (lint + typecheck + test)
- AWS deploy in `docs/PRODUCTION_ROADMAP.md`, not built

## License

MIT. See `LICENSE`.
