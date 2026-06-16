# EverCurrent

EverCurrent is an agentic AI layer for hardware engineering teams. It
ingests Slack channels and Dropbox PDFs, routes every event
through a Haiku-tier classifier, builds Knowledge Cards from the
signal, and writes a personalised morning briefing per engineer per
day. The product is not a chatbot — it is the autonomous worker behind
every screen, so two short visits a day replace the open-tab firehose.

## Status

The core product is built and runnable: Slack + Dropbox ingestion, Haiku
router tagging, Sonnet Knowledge Cards, the pure-Python scoring engine,
per-user Sonnet digests, the dashboard with SSE live updates, pgvector
RAG, Slack DM delivery, the proactive Eve agent, the timeline/Gantt +
blocker board, and an offline eval harness.

Roadmap: linker agent (cross-source edges), a dashboard chat agent,
critical-path what-if on the timeline, more connectors (GitHub / Jira /
Email), and AWS deploy (ECS + RDS + ElastiCache).

Docs: `docs/ARCHITECTURE.md` (design rationale),
`docs/SYSTEM_DESIGN.md` (runtime flows), `docs/SCALING.md` (gaps +
hardening), `docs/INTERVIEW_PREP.md` (question bank).

## Quick start

```bash
cp .env.example .env          # fill ANTHROPIC_API_KEY, VOYAGE_API_KEY, Auth0, Slack
make up-monitor               # stack + Prometheus + Loki + Grafana
make migrate                  # apply schema
open http://localhost:3000    # dashboard
open http://localhost:3030    # grafana (default admin / admin)
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
The rest is pure Python. Design rationale in `docs/ARCHITECTURE.md`.

## Read order

`docs/ARCHITECTURE.md` is the single design doc — backend architecture,
data flow, and the rationale behind the major choices. The code is the
source of truth for everything else.

## Try the agent yourself

This works on a real Slack workspace in about two minutes.

1. Create a Slack app at https://api.slack.com/apps. Bot scopes:
   `chat:write`, `channels:history`, `groups:history`. Install to your
   workspace, copy the bot token (`xoxb-...`).
2. Create channels `#mech-design`, `#qa-testing`, `#supply-chain`,
   `#general`. Invite the bot to each.
3. Connect the workspace via the Dropbox/Slack OAuth install flow, then
   post a few cross-subsystem messages in those channels by hand.
4. Open the dashboard. Pick a member. Click "Regenerate digest." Watch
   Sonnet draft a three-section briefing with citation pills.
5. Post a new message in one of the channels describing a decision, risk,
   or question — e.g. a part swap, a spec change, or a blocker.
6. Within a couple of seconds a Card appears on the dashboard, tagged with
   its topic, urgency, and the entities the router extracted, linking back
   to the source Slack message.

## Verification

```bash
make lint            # ruff + ty (api), eslint + prettier + tsc (web)
make test            # unit tests — deterministic layers
make eval            # router + scoring + rag + digest + eve evals
```

`make eval` runs all evals; it skips the LLM and Voyage ones if API keys
are not set. Evals are not in CI by design — cost and nondeterminism.

## Stack

Backend: Python 3.13, FastAPI 0.136, SQLAlchemy 2.0 async, Postgres 17
+ pgvector 0.8, Celery 5.4 + Beat, Anthropic SDK (Claude Sonnet 4.6,
Haiku 4.5), Voyage `voyage-3-lite` (512 dim), structlog, ruff + ty.

Frontend: Node 25, Next.js 16.2 App Router, React 19, TypeScript 5
strict, Tailwind v4, shadcn/ui, TanStack Query v5, Zustand, Zod.

Infra (local only): Docker + docker-compose, Prometheus + Loki +
Grafana for observability.
