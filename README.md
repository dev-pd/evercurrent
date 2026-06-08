# EverCurrent

EverCurrent is an agentic AI layer for hardware engineering teams. It
ingests Slack channels and Google Drive PDFs, routes every event
through a Haiku-tier classifier, builds Knowledge Cards from the
signal, and writes a personalised morning briefing per engineer per
day. The product is not a chatbot — it is the autonomous worker behind
every screen, so two short visits a day replace the open-tab firehose.

> A 90-second demo would walk: post a Slack message from a phone, watch
> a Card slide into the dashboard within a second; click "regenerate"
> on the digest, see three priority buckets with citation pills that
> resolve back to the source Slack message and the Drive PDF.

## What's built vs what's roadmap

| Phase | Scope                                                       | Status |
|-------|-------------------------------------------------------------|--------|
| 0     | Codebase reset for v2 architecture                          | done   |
| 1     | Infra: docker-compose, plugins, Makefile, dev setup         | done   |
| 2     | Auth0 + Postgres RLS + multi-tenancy                        | done   |
| 3     | Slack OAuth + Events API + backfill                         | done   |
| 4     | MCP tool layer (search_messages, search_documents, etc.)    | done   |
| 5     | Router agent (Haiku) + per-message enrichment               | done   |
| 6     | Knowledge Cards (Sonnet draft, deterministic build rules)   | done   |
| 7     | Scoring engine (pure Python, six signals)                   | done   |
| 8     | Digest agent (Sonnet, per-user, idempotent)                 | done   |
| 9     | Dashboard FE — cards-first, SSE live updates                | done   |
| 10    | Drive connector + PDF ingest + pgvector RAG                 | done   |
| 11    | Slack DM delivery + Subscriptions + quiet hours             | done   |
| 12    | Eval harness + demo script + this README                    | done   |
| —     | Linker agent (cross-source edges)                           | roadmap |
| —     | Chat agent on the dashboard                                 | roadmap |
| —     | Timeline / Gantt + critical-path what-if                    | roadmap |
| —     | AWS deploy (ECS + RDS + ElastiCache)                        | roadmap |
| —     | GitHub + Jira + Email connectors                            | roadmap |
| —     | Phase agent + Personalizer                                  | roadmap |

`docs/PRODUCTION_ROADMAP.md` has the full post-take-home plan.

## Quick start

```bash
cp .env.example .env          # fill ANTHROPIC_API_KEY, VOYAGE_API_KEY, Auth0, Slack
make up-monitor               # stack + Prometheus + Loki + Grafana
make migrate                  # apply schema
open http://localhost:3000    # dashboard
open http://localhost:3001    # grafana (default admin / admin)
```

The dashboard opens to an empty state. Use the Slack tutorial below to
get your first Card on screen in two minutes.

## Architecture

```
                    +---------------------+
                    |       Browser       |
                    | Next.js + SSE       |
                    +----------+----------+
                               |
                               v
+------------------------------+------------------------------+
|                          FastAPI                            |
|  Auth0 -> RLS context -> routes -> services -> repositories |
+------+----------------+---------------------+---------------+
       |                |                     |
       v                v                     v
+--------------+   +----------+   +---------------------+
| Postgres 17  |   |  Redis   |   |   Celery + Beat     |
| + pgvector   |   |  Pub/Sub |<--|   Background jobs   |
+--------------+   +----------+   +----------+----------+
                                             |
                            +----------------+----------------+
                            v                                 v
                   +-----------------+              +-------------------+
                   |   Anthropic     |              |   Voyage AI       |
                   | Haiku + Sonnet  |              |  voyage-3-lite    |
                   +-----------------+              +-------------------+
```

Two agents, not one mega-agent. Router (Haiku, per-message) classifies
and tags. Digest (Sonnet, per-user-per-morning) writes the briefing.
The rest is pure Python. Decision rationale in `docs/DECISIONS.md`.

## Read order

A reviewer with 30 minutes should open these four docs in order:

1. **`docs/PRD.md`** — what we built and a day-in-the-life walkthrough.
2. **`docs/SYSTEM_DESIGN.md`** — data model, API surface, request
   lifecycle.
3. **`docs/DECISIONS.md`** — every architectural choice as an ADR.
4. **`docs/AGENT_VS_WORKFLOW.md`** — what the agent decides, what the
   workflow does.

Then `docs/CODE_TOUR.md` if they want a file-by-file walk before
opening the codebase.

`docs/phases/` is the build journal — one short doc per phase. Useful
for understanding the order of decisions; not required reading.

## Try the agent yourself

This works on a real Slack workspace in about two minutes.

1. Create a Slack app at https://api.slack.com/apps. Bot scopes:
   `chat:write`, `channels:history`, `groups:history`. Install to your
   workspace, copy the bot token (`xoxb-...`).
2. Create channels `#mech-design`, `#qa-testing`, `#supply-chain`,
   `#general`. Invite the bot to each.
3. `export SLACK_DEMO_BOT_TOKEN=xoxb-...`
4. `make slack-seed` — posts 30 days of hardware-team backfill messages.
5. Open the dashboard. Pick a member. Click "Regenerate digest." Watch
   Sonnet draft a three-section briefing with citation pills.
6. Post a new message in `#mech-design` from your phone: *"Decided:
   switching BRK-A1 to AL-7075-T6. ECO-178 drafted."*
7. Within ~2 seconds a Card appears on the dashboard with topic `eco`,
   urgency `high`, entities `[BRK-A1, AL-7075-T6, ECO-178]`. The
   linked Slack thread is one click away.

## Verification

```bash
make lint            # ruff + ty (api), eslint + prettier + tsc (web)
make test            # /health + /ready unit tests
make eval            # router + scoring + rag + digest evals
```

`make eval` runs all four evals; skips the LLM and Voyage ones if API
keys are not set. Numbers are documented in `docs/EVAL_BASELINE.md`.
Evals are not in CI by design — cost and nondeterminism. See ADR-013.

## Stack

Backend: Python 3.13, FastAPI 0.136, SQLAlchemy 2.0 async, Postgres 17
+ pgvector 0.8, Celery 5.4 + Beat, Anthropic SDK (Claude Sonnet 4.6,
Haiku 4.5), Voyage `voyage-3-lite` (512 dim), structlog, ruff + ty.

Frontend: Node 25, Next.js 16.2 App Router, React 19, TypeScript 5
strict, Tailwind v4, shadcn/ui, TanStack Query v5, Zustand, Zod.

Infra (local only): Docker + docker-compose, Prometheus + Loki +
Grafana for observability. AWS deploy in `docs/PRODUCTION_ROADMAP.md`.

## License

MIT. See `LICENSE`.
