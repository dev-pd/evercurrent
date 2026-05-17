# EverCurrent — Build Doc

> An agentic AI layer for hardware engineering teams. Personalizes information by role, project phase, and behavior. Tracks cross-functional dependencies. Extracts structured decisions from team chatter. Answers questions by reasoning across team docs and conversations.

This is the build plan for the EverCurrent take-home. Structured for execution by Claude Code, phase by phase, subphase by subphase. Every subphase has a goal, concrete tasks, and a definition of done. Do not skip ahead. Verify each definition of done before moving on.

---

## Table of contents

- 1. Project framing
- 2. Tech stack (locked versions, May 2026)
- 3. Repository layout
- 4. Coding standards (the bar)
- 5. Phase 0 — Scaffolding and dev environment
- 6. Phase 1 — Data model and synthetic data seeder
- 7. Phase 2 — Aggregator pipeline
- 8. Phase 3 — RAG over project docs
- 9. Phase 4 — Agent layer with 6 tools
- 10. Phase 5 — Frontend dashboard and chat panel
- 11. Phase 6 — Multi-day simulation and timeline
- 12. Phase 7 — Decision extraction
- 13. Phase 8 — Eval harness
- 14. Phase 9 — Production polish
- 15. Whole-project definition of done
- 16. Demo script

---

## 1. Project framing

**The brief.** Hardware engineering teams (mech, EE, supply chain, PM, QA) live in Slack. Important updates get buried. Every role has different priorities, and priorities shift as the project progresses through phases (concept, design, EVT, DVT, PVT, MP). Build a tool that surfaces the most relevant information for each role and adapts as priorities change.

**Why this framing.** EverCurrent's positioning is not just summarization. It is extracting decisions (what was decided, why, by whom, what it depends on) and surfacing cross-functional dependencies (a supply chain delay that affects a mech engineer's design choice). The build reflects this posture directly.

**What we build.** A working prototype:

- Synthetic Slack-like messages and project documents
- Per-message enrichment (topic, urgency, affected roles, entities)
- Per-user scoring with role, phase, dependency, and learned feedback weights
- Personalized daily digest with citations
- Structured decision extraction from messages
- Multi-day simulation showing digests evolving as feedback and phase shift
- RAG over project docs (PRD, BOM, ECO log, test reports)
- Multi-source reasoning agent with 6 tools and streaming responses
- Phase timeline view showing digest evolution across the simulated week
- Per-user feedback loop (thumbs up/down adjusts weights)
- Eval harness with retrieval, scoring, digest quality, decision extraction
- Production roadmap doc covering scale-out, compliance, observability

---

## 2. Tech stack (locked versions, May 2026)

### Backend

| Concern | Choice | Version | Notes |
|---|---|---|---|
| Language | Python | 3.13 | Latest stable. |
| Package manager | uv | latest | Astral. Replaces pip, poetry, virtualenv. |
| Web framework | FastAPI | 0.136.1 | Pin `>=0.136.1,<0.137.0`. |
| ASGI server | uvicorn | latest | Run via `fastapi run` for prod, `fastapi dev` for dev. |
| Validation | Pydantic | 2.12+ | Strict mode everywhere. |
| ORM | SQLAlchemy | 2.0 async | Async sessions only. |
| Migrations | Alembic | latest | Autogenerate from models. |
| Database | Postgres | 17 | Latest stable. |
| Vector extension | pgvector | 0.8+ | Cosine + HNSW. |
| Job queue | Arq | latest | Async Redis queue, fits FastAPI naturally. |
| Cache + queue | Redis | 7.4 | |
| LLM SDK | anthropic (Python) | latest | Claude Sonnet 4.6 + Haiku 4.5 tiered. |
| Embeddings | Voyage AI | `voyage-3-lite` | 512 dims. Anthropic-partnered. |
| Logging | structlog | latest | JSON output. |
| Tracing | OpenTelemetry SDK | latest | Instrumented, exporter wired but not shipped. |
| HTTP client | httpx | latest | Async. |
| DI | dependency-injector | latest | Lightweight DI container. |
| Linting + format | ruff | latest | One tool replaces flake8, black, isort, pylint. |
| Type checking | ty | latest | Astral. Replaces mypy. Fast. |
| Testing | pytest + pytest-asyncio | latest | `asyncio_mode = "auto"`. |
| Coverage | pytest-cov | latest | Fail under 70%. |
| Pre-commit | pre-commit | latest | ruff + ty on every commit. |

### Frontend

| Concern | Choice | Version | Notes |
|---|---|---|---|
| Language | TypeScript | 5.x strict | No `any`. |
| Runtime | Node | 25.x | Latest stable (bumped from doc default of 22 LTS — local env has v25.9). |
| Package manager | pnpm | latest | |
| Framework | Next.js | 16.2 | App Router. Turbopack default. React Compiler stable. |
| UI library | React | 19 | With React Compiler enabled. |
| Styling | Tailwind | v4 | |
| Components | shadcn/ui | latest | Copy-paste, full control. |
| Server state | TanStack Query | v5 | |
| Client state | Zustand | latest | Only where needed. |
| Validation | Zod | latest | Schemas via OpenAPI codegen from backend. |
| Lint + format | ESLint + Prettier | latest | Strict config. |
| Testing | Vitest + Playwright | latest | Unit + E2E. |

### Infra (local only)

| Concern | Choice | Notes |
|---|---|---|
| Containers | Docker + docker-compose | Local dev: api + worker + web + postgres + redis. Multi-stage Dockerfiles. |
| CI | GitHub Actions | Lint + type-check + test + build on PR. |

No Pulumi, no Terraform. Production deployment story is covered as prose with a high-level architecture diagram in `docs/PRODUCTION_ROADMAP.md`.

---

## 3. Repository layout

Monorepo, backend (`apps/api`) and frontend (`apps/web`) at top level.

```
evercurrent/
├── apps/
│   ├── api/                          Python FastAPI backend
│   │   ├── src/evercurrent/
│   │   │   ├── main.py               FastAPI app factory
│   │   │   ├── config.py             Pydantic Settings
│   │   │   ├── deps.py               DI container wiring
│   │   │   ├── domain/               Pure domain models, no I/O
│   │   │   │   ├── projects.py
│   │   │   │   ├── users.py
│   │   │   │   ├── messages.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── decisions.py
│   │   │   │   └── digests.py
│   │   │   ├── db/
│   │   │   │   ├── session.py
│   │   │   │   ├── models.py
│   │   │   │   └── repositories/
│   │   │   │       ├── projects.py
│   │   │   │       ├── users.py
│   │   │   │       ├── messages.py
│   │   │   │       ├── documents.py
│   │   │   │       ├── decisions.py
│   │   │   │       ├── digests.py
│   │   │   │       └── feedback.py
│   │   │   ├── ingestion/
│   │   │   │   ├── seeder.py
│   │   │   │   ├── narrative.py      multi-day narrative continuity
│   │   │   │   └── prompts/
│   │   │   │       ├── messages_day.txt
│   │   │   │       └── docs.txt
│   │   │   ├── enrichment/
│   │   │   │   ├── tagger.py
│   │   │   │   ├── schemas.py        tag output schema
│   │   │   │   └── prompts/tag_message.txt
│   │   │   ├── scoring/
│   │   │   │   ├── engine.py
│   │   │   │   ├── weights.py
│   │   │   │   └── dependencies.py   cross-functional match logic
│   │   │   ├── digest/
│   │   │   │   ├── generator.py
│   │   │   │   └── prompts/generate.txt
│   │   │   ├── decisions/
│   │   │   │   ├── extractor.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── prompts/extract.txt
│   │   │   ├── rag/
│   │   │   │   ├── chunker.py
│   │   │   │   ├── embedder.py
│   │   │   │   ├── indexer.py
│   │   │   │   └── retriever.py
│   │   │   ├── agent/
│   │   │   │   ├── tools.py
│   │   │   │   ├── runner.py
│   │   │   │   ├── streaming.py
│   │   │   │   └── prompts/system.txt
│   │   │   ├── jobs/
│   │   │   │   ├── worker.py
│   │   │   │   └── tasks/
│   │   │   │       ├── enrich_messages.py
│   │   │   │       ├── generate_digests.py
│   │   │   │       ├── extract_decisions.py
│   │   │   │       ├── advance_day.py
│   │   │   │       └── ingest_doc.py
│   │   │   ├── api/
│   │   │   │   ├── routes/
│   │   │   │   │   ├── health.py
│   │   │   │   │   ├── users.py
│   │   │   │   │   ├── projects.py
│   │   │   │   │   ├── digests.py
│   │   │   │   │   ├── feedback.py
│   │   │   │   │   ├── agent.py
│   │   │   │   │   ├── simulation.py
│   │   │   │   │   ├── decisions.py
│   │   │   │   │   └── timeline.py
│   │   │   │   ├── schemas.py
│   │   │   │   ├── middleware.py     request ID, logging context
│   │   │   │   └── errors.py
│   │   │   └── llm/
│   │   │       ├── client.py
│   │   │       └── tiering.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── evals/
│   │   ├── alembic/versions/
│   │   ├── seed_data/                committed, deterministic
│   │   │   ├── project.json
│   │   │   ├── users.json
│   │   │   ├── messages_day_1.json ... messages_day_5.json
│   │   │   └── docs/
│   │   │       ├── prd.md
│   │   │       ├── bom.md
│   │   │       ├── eco_log.md
│   │   │       ├── test_report_thermal.md
│   │   │       └── test_report_drop.md
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── .env.example
│   │
│   └── web/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx              redirects /dashboard
│       │   ├── dashboard/page.tsx
│       │   ├── timeline/page.tsx
│       │   └── decisions/page.tsx
│       ├── components/
│       │   ├── ui/                   shadcn
│       │   ├── digest/
│       │   ├── chat/
│       │   ├── simulation/
│       │   ├── timeline/
│       │   ├── decisions/
│       │   └── layout/
│       ├── lib/
│       │   ├── api.ts
│       │   ├── stream.ts
│       │   └── types.ts
│       ├── hooks/
│       ├── stores/
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── package.json
│       ├── Dockerfile
│       └── README.md
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CONTRIBUTING.md
│   ├── PRODUCTION_ROADMAP.md
│   ├── LEARNING_NOTES.md
│   ├── EVAL_BASELINE.md
│   └── DEMO_SCRIPT.md
│
├── docker-compose.yml
├── Makefile
├── .pre-commit-config.yaml
├── .gitignore
├── .editorconfig
└── README.md
```

---

## 4. Coding standards (the bar)

Non-negotiable.

### Architecture

- **Layered.** Routes → services → repositories → database. No SQL in routes, no HTTP in services.
- **Pure domain models** in `domain/`, no I/O. SQLAlchemy models in `db/` map to/from domain.
- **Dependency injection.** All side-effecting collaborators injected via FastAPI `Depends()` or `dependency-injector`. No globals.
- **Adapter pattern.** `EmbeddingProvider` interface with `VoyageEmbedder` implementation. `LLMProvider` interface with `AnthropicProvider` implementation.
- **Self-contained modules.** Each service module owns its domain end-to-end.

### Python

- Type hints on every function signature and return type.
- No `Any` except where genuinely dynamic, with `# type: ignore` and a comment.
- Pydantic v2 strict mode on all schemas.
- Async/await for all I/O.
- `asyncio.TaskGroup` for structured concurrency.
- Connection pool management via FastAPI lifespan.
- structlog for all logging. JSON output.
- Request ID propagation through logs.
- Graceful shutdown handlers for SIGTERM.
- `ruff check` and `ty check` clean before commit.
- `pyproject.toml` as single source of truth.

### TypeScript

- `strict: true`. No `any`.
- Zod schemas at every external boundary.
- Server components by default in Next.js. Client components only where needed.
- TanStack Query for all server state. No `useEffect` for data fetching.
- Tailwind only. No CSS-in-JS.
- Lucide icons via shadcn. No emojis in code.

### Testing

- Unit tests on scoring engine, chunker, weight calculations.
- Integration test on end-to-end pipeline (seed → enrich → score → generate).
- Eval harness with 4 categories.
- 70%+ coverage on `scoring/`, `rag/chunker.py`, `decisions/`.
- Vitest for frontend unit tests.
- Playwright for one happy-path E2E.

### Git

- Conventional Commits (`feat:`, `fix:`, etc.).
- Atomic commits. One logical change per commit.
- Branches named `feat/phase-N.M-description`.
- Pre-commit hooks run ruff + ty + prettier + eslint.

### Documentation

- Every module has a docstring.
- Every non-obvious public function has arg/return docs.
- README in every top-level directory.
- ARCHITECTURE.md is the source of truth for design decisions.

---

## 5. Phase 0 — Scaffolding and dev environment

> Get the foundation right before any product code. An extra hour here saves five hours later.

### 0.1 Repository bootstrap

**Goal.** Empty repo with both apps scaffolded, both apps starting.

**Tasks.**
- `git init`, top-level `.gitignore` (Python, Node, IDE, env), `.editorconfig`, `LICENSE` (MIT), top-level `README.md` stub
- `apps/api/`: `uv init`, set Python to 3.13, write `pyproject.toml` with full dependency list from §2
- `apps/web/`: `pnpm create next-app@latest` (TypeScript, App Router, Tailwind, no `src/`, no ESLint default — we add stricter manually)
- Verify both apps start in isolation (`fastapi dev` in api, `pnpm dev` in web)

**Definition of done.**
- `cd apps/api && uv sync && uv run fastapi dev src/evercurrent/main.py` serves a placeholder `/health` returning `{"status": "ok"}`
- `cd apps/web && pnpm dev` serves the Next.js starter at `localhost:3000`

### 0.2 Docker Compose stack

**Goal.** One command brings up the full local environment.

**Tasks.**
- Write `docker-compose.yml` with services: `postgres` (image `pgvector/pgvector:pg17`), `redis` (image `redis:7.4-alpine`), `api`, `worker` (same image as api, runs `arq evercurrent.jobs.worker.WorkerSettings`), `web`
- Healthchecks on `postgres` and `redis`
- Multi-stage `apps/api/Dockerfile` (builder layer installs uv and deps, runtime layer uses distroless or slim Python 3.13)
- Multi-stage `apps/web/Dockerfile` (builder runs `pnpm build` with Next standalone output, runtime uses Node 22 alpine)
- `.env.example` at repo root with `ANTHROPIC_API_KEY=` and `VOYAGE_API_KEY=` placeholders
- Top-level `README.md` with "Quickstart" section: prereqs, `cp .env.example .env`, fill in keys, `make up`, open localhost:3000

**Definition of done.**
- `docker compose up` from a fresh clone (with `.env` set) brings everything up
- `curl http://localhost:8000/health` returns 200
- `curl http://localhost:3000` returns HTML
- `docker compose down` cleans up

### 0.3 Tooling: lint, format, type check, pre-commit

**Goal.** Standards enforced automatically on every commit.

**Tasks.**
- `apps/api`: configure `ruff` (target py313, line length 100, select ALL, ignore D/ANN101/ANN102/COM812/ISC001) and `ty` in `pyproject.toml`
- `apps/web`: configure ESLint (strict) and Prettier
- Root `.pre-commit-config.yaml` with hooks: `ruff format`, `ruff check --fix`, `ty check`, `prettier --write` (web), `eslint --fix` (web)
- `pre-commit install` documented in README
- Commit a deliberately-broken file, verify hooks catch it, then fix

**Definition of done.**
- `pre-commit run --all-files` passes on a clean repo
- A bad commit (missing type hint, unused import) is rejected by the hook

### 0.4 Makefile and dev ergonomics

**Goal.** Common commands one keystroke away.

**Tasks.**
- Root `Makefile` with targets:
  - `up` — `docker compose up -d`
  - `down` — `docker compose down`
  - `logs` — `docker compose logs -f`
  - `seed` — runs seeder script inside api container
  - `migrate` — runs `alembic upgrade head`
  - `migration name=...` — creates new migration
  - `ingest-docs` — runs RAG ingestion
  - `generate-digests day=N` — runs digest generation for day N
  - `test` — `pytest` in api, `vitest` in web
  - `eval` — runs eval harness
  - `lint` — runs ruff + ty + eslint
  - `fmt` — runs ruff format + prettier
  - `web` — `pnpm dev` in apps/web
  - `api` — `fastapi dev` in apps/api
- `.editorconfig` aligned with ruff settings

**Definition of done.**
- `make` lists all targets
- Every target runs without error (where applicable on empty project)

### 0.5 CI scaffolding

**Goal.** Pull requests are gated by lint, type check, test, build.

**Tasks.**
- `.github/workflows/ci.yml` with jobs: `lint-api` (ruff + ty), `lint-web` (eslint + prettier check), `test-api` (pytest, with postgres + redis services), `test-web` (vitest), `build-api` (docker build), `build-web` (docker build)
- All jobs run on PR
- Cache uv and pnpm for speed

**Definition of done.**
- A test PR to a feature branch shows the CI checks running and passing
- Failure on any check blocks merge

---

## 6. Phase 1 — Data model and synthetic data seeder

### 6.1 Database schema and migrations

**Goal.** Schema designed for the full feature set, ready for multi-project (we ship one project).

**Tasks.**
- Define SQLAlchemy 2.0 declarative models in `db/models.py` for: `projects`, `users`, `channels`, `messages`, `message_tags`, `documents`, `document_chunks` (with `Vector(512)` column), `decisions`, `digests`, `feedback`
- Set up Alembic in `apps/api/alembic/`, autogenerate the initial migration
- Migration must `CREATE EXTENSION vector`
- Add HNSW index on `document_chunks.embedding`, GIN index on `document_chunks.metadata`
- Async session factory in `db/session.py` with FastAPI lifespan integration

**Definition of done.**
- `make migrate` on empty DB produces all tables and the vector extension
- A roundtrip test inserts and reads a `document_chunk` with a vector

### 6.2 Domain models and repositories

**Goal.** Clean separation between domain and persistence.

**Tasks.**
- Pydantic v2 domain models in `domain/` matching each table conceptually (not 1:1, e.g. `EnrichedMessage` joins `messages` + `message_tags`)
- Repository pattern in `db/repositories/` with async methods: `MessageRepository.get_by_day`, `UserRepository.get_by_id`, etc.
- Repository methods take and return domain models, not SQLAlchemy models
- Unit tests with an async test fixture spinning up a real Postgres (testcontainers or docker-compose service)

**Definition of done.**
- Each repository has at least 3 methods (get by id, list with filter, create/update)
- All repository tests pass against a real Postgres
- Domain models have zero SQLAlchemy imports

### 6.3 Project, users, channels seed

**Goal.** Static seed data (project, users, channels) committed and loaded.

**Tasks.**
- Hand-write `apps/api/seed_data/project.json` with: name "Warehouse Robot v2", current_phase "DVT", phase_concerns map (DVT → ["thermal margin", "yield rate", "test failures", "ECO velocity"], PVT → ["first article", "manufacturing yield", "supplier quality"], etc.), milestones array
- Hand-write `apps/api/seed_data/users.json` with 8 users: Sarah (mech lead, owns: chassis, mounting, brackets), Raj (EE lead, owns: power board, motor drivers), Mei (supply chain, owns: BOM, suppliers), David (PM), Lin (test engineer), Tom (firmware), Priya (mech, owns: arms, gripper), Carlos (procurement)
- Hand-write 5 channels: `#mech-design`, `#electrical`, `#supply-chain`, `#qa-testing`, `#general`
- `seeder.py` loads these JSON files into the DB via repositories
- `make seed` loads everything fresh

**Definition of done.**
- After `make seed`, `SELECT * FROM users` returns 8 rows, `projects` returns 1, `channels` returns 5
- Re-running `make seed` is idempotent (or cleanly resets)

### 6.4 Synthetic messages generation

**Goal.** 5 days of narratively coherent messages, pre-generated and committed.

**Tasks.**
- `ingestion/narrative.py` defines the 5-day arc: Day 1 establishes thermal cycling failure investigation, supplier strike on aluminum extrusion, ongoing ECO discussion. Day 2 thermal investigation continues, new firmware bug discovered. Day 3 root cause hypothesis, supplier finds workaround. Day 4 ECO approved, first article inspection. Day 5 partial resolution, new risk emerges.
- `ingestion/prompts/messages_day.txt` is the prompt template (see prompt sketch below)
- `seeder.py --generate-messages` calls Haiku 5 times (one per day), passing the previous day's summary as context. Output goes to `seed_data/messages_day_N.json`
- Each generated message has: `channel`, `author_username`, `text`, `ts` (within the day), optional `thread_root_id`, optional `reactions`
- Aim for ~50 messages per day = 250 total
- Commit the generated JSON files to the repo for determinism
- A separate command `make seed-messages` (which calls `seeder.py --load-messages`) loads them into DB

**Prompt sketch (`messages_day.txt`):**
```
You generate realistic Slack messages for day {day_number} of a hardware project.

Project: Warehouse Robot v2, currently in DVT phase.
Users and roles: {users_json}
Channels: {channels_list}

What happened in the project so far:
{prior_days_summary}

Themes to continue for day {day_number}:
{day_themes}

Generate ~50 messages covering the themes. Some messages should be in threads
(set thread_root_id to an earlier message's id). Use hardware engineering
vocabulary (DVT, ECO, BOM, yield, first article, thermal margin, etc.).
Be technical and realistic.

Output: a JSON array of message objects with fields:
- channel
- author_username
- text
- ts (ISO 8601, within day {day_number})
- thread_root_id (optional, references another message's id from this day or
  an earlier day)
- reactions (optional, array of emoji names)
```

**Definition of done.**
- All 5 `messages_day_N.json` files committed
- After `make seed-messages`, the DB has 250+ messages with realistic content
- Messages reference real channels and real users
- Some messages are threaded

### 6.5 Synthetic project documents generation

**Goal.** 5 project docs that the RAG layer can index.

**Tasks.**
- `seeder.py --generate-docs` produces 5 markdown files in `seed_data/docs/`:
  - `prd.md` — Product Requirements Doc (2 pages): goals, user requirements, performance targets, key specs (motor torque, battery life, payload, IP rating)
  - `bom.md` — Bill of Materials (1 page): table of ~20 critical parts (motor M-2401, aluminum extrusion AL-6063-T5, battery cell BC-18650, etc.) with vendor, lead time, cost
  - `eco_log.md` — Engineering Change Order log (1-2 pages): 10 entries with ECO number, date, originator, change description, affected subsystems, status
  - `test_report_thermal.md` — Thermal cycling test report (1 page): test setup, results, pass/fail criteria, anomalies observed
  - `test_report_drop.md` — Drop test report (1 page): similar structure
- Use Sonnet for these (better long-form generation)
- Commit the generated markdown
- `seeder.py --load-docs` loads them as `documents` rows (body = file contents)

**Definition of done.**
- All 5 markdown files exist in `seed_data/docs/`
- Each is ≥ 1 page of realistic content
- After `make seed-docs`, the DB has 5 `documents` rows

### 6.6 Wire the full seed flow

**Goal.** One `make seed` does everything.

**Tasks.**
- `make seed` runs: `migrate` → `seed-base` (project, users, channels) → `seed-messages` → `seed-docs`
- Make it idempotent or have `make reset` that truncates + reseeds
- Document the flow in `apps/api/README.md`

**Definition of done.**
- `make reset && make seed` on a fresh DB produces a fully populated dataset in under 30 seconds (since LLM generation is already done)

---

## 7. Phase 2 — Aggregator pipeline

### 7.1 Anthropic client and model tiering

**Goal.** Single client wrapper handles Haiku vs Sonnet selection cleanly.

**Tasks.**
- `llm/client.py` exposes `LLMProvider` interface with methods `tag()`, `generate_digest()`, `extract_decisions()`, `chat_with_tools()`
- `llm/tiering.py` defines model assignments: tagging uses `claude-haiku-4-5-20251001`, digest + decisions + agent use `claude-sonnet-4-6`
- Structured output via Anthropic's tool use or strict JSON schema (use `response_format` or fallback to JSON-mode prompting with Pydantic validation)
- Retry with exponential backoff on transient errors (httpx + tenacity)
- All calls go through this client. No raw `anthropic.AsyncAnthropic()` elsewhere.

**Definition of done.**
- A simple unit test calls `tag()` with a sample message and gets a valid structured tag back

### 7.2 Message enrichment

**Goal.** Every message gets topic, urgency, affected roles, and entities.

**Tasks.**
- `enrichment/schemas.py` defines `MessageTag` Pydantic model: `topic` (Literal of ~15 categories like `supply_chain_disruption`, `quality_issue`, `design_change`, `firmware_bug`, etc.), `urgency` (Literal `low|medium|high|critical`), `affected_roles` (list of role enums), `entities` (list of strings: part numbers, supplier names, subsystems)
- `enrichment/prompts/tag_message.txt` prompt
- `enrichment/tagger.py`: `async def tag_message(message: Message) -> MessageTag`
- `jobs/tasks/enrich_messages.py`: Arq task `enrich_day(day: int)` that enriches all messages for a day, stores results in `message_tags`
- Batch within the day (10-20 messages per LLM call) to reduce cost
- Cache: if a message's tag already exists in DB, skip

**Prompt sketch:**
```
You analyze Slack messages from a hardware engineering team.

Tag each message with:
- topic: one of [supply_chain_disruption, quality_issue, design_change,
  firmware_bug, test_result, schedule_risk, eco, supplier_issue,
  thermal, mechanical, electrical, ...]
- urgency: low | medium | high | critical
- affected_roles: which roles should care (mech_eng, ee, supply_chain, pm,
  qa, firmware)
- entities: parts, suppliers, subsystems mentioned

Messages:
{messages_json}

Return a JSON array of tags, one per input message, in order.
```

**Definition of done.**
- Running `enrich_day(1)` produces tags for all day 1 messages
- A spot check: a message about thermal failure gets `topic=quality_issue`, `urgency=high`, `affected_roles=[mech_eng, ee, qa]`, `entities=[chassis, thermal cycling]`
- Cost per day < $0.10 (Haiku is cheap)

### 7.3 Scoring engine and weights

**Goal.** Pure-Python per-user message scoring.

**Tasks.**
- `scoring/weights.py` defines weight constants:
  - `ROLE_DIRECT = 10.0` (user's role is in `affected_roles`)
  - `CROSS_FUNCTIONAL = 7.0` (user owns a subsystem/part in `entities`)
  - `URGENCY = {low: 0, medium: 2, high: 5, critical: 10}`
  - `THREAD_ACTIVITY = 2.0` (5+ thread replies)
- `scoring/dependencies.py` exports `dependency_match(entities, owned_subsystems, owned_parts) -> bool` with fuzzy matching (lowercase, substring + simple synonym map like "extrusion" → "aluminum extrusion")
- `scoring/engine.py` exports `score_message(msg, user, project) -> float` per the formula in §1
- `score_all_for_user(user, day) -> list[ScoredMessage]` returns top-N sorted
- Fully unit-tested in `tests/unit/test_scoring.py`: cases for role-only match, dependency-only match, both, phase weight, feedback weight, ordering invariants

**Definition of done.**
- 10+ unit tests in `test_scoring.py`, all passing
- `score_all_for_user(sarah, day=1)` returns a list where the top 3 are visibly mech-relevant

### 7.4 Digest generation

**Goal.** Per-user personalized digest as markdown with citations.

**Tasks.**
- `digest/generator.py`: `async def generate_digest(user, day, top_messages, project) -> str` returns markdown
- `digest/prompts/generate.txt` prompt (see sketch below)
- Output stored in `digests` table with `content_md` and `item_message_ids`
- `jobs/tasks/generate_digests.py`: Arq task `generate_all_digests(day)` that scores + generates for each user

**Prompt sketch:**
```
You write a personalized morning briefing for a hardware engineer.

User: {user.name}, role: {user.role}
Owned subsystems: {user.owned_subsystems}

Project: {project.name}
Current phase: {project.current_phase}
Days until "{project.next_milestone}": {days_until}

Today's top items (ranked by relevance):
{top_messages_json}

Write a briefing that:
1. Groups items by theme (Top priority / Watch-outs / FYI)
2. Leads with the most actionable
3. Includes a one-line "why this matters to you" per item
4. Uses bullet points
5. Cites source messages by id like [msg_142]
6. Stays under 250 words
7. Uses second person ("you")
8. No fluff, no preamble, no "good morning"
```

**Definition of done.**
- After running `generate_all_digests(day=3)`, querying `digests` for user_id=Sarah returns a markdown briefing
- Briefing cites real message IDs that exist in the DB
- Briefing is ≤ 250 words
- Briefings for different users are visibly different in content

### 7.5 API endpoints for digests

**Goal.** Frontend can fetch and trigger digests.

**Tasks.**
- `api/routes/digests.py`:
  - `POST /digests/generate?day=N` — enqueues Arq task, returns 202 with job id
  - `GET /digests/{user_id}?day=N` — returns the stored digest
- `api/routes/feedback.py`:
  - `POST /feedback` body `{user_id, message_id, signal: +1|-1}` — stores feedback, updates `user.topic_weights[topic]` by `± FEEDBACK_DELTA`
- Pydantic response schemas with strict mode
- Standard error responses

**Definition of done.**
- `curl -X POST localhost:8000/digests/generate?day=3` returns 202
- After job completes, `curl localhost:8000/digests/{sarah_id}?day=3` returns the digest
- Posting feedback updates the user's topic_weights

### 7.6 Integration test

**Goal.** End-to-end pipeline verified.

**Tasks.**
- `tests/integration/test_pipeline.py` spins up Postgres + Redis, runs: seed → enrich day 1 → generate digests day 1 → assertions on output
- Test runs in CI

**Definition of done.**
- The integration test passes locally and in CI in under 2 minutes

---

## 8. Phase 3 — RAG over project docs

### 8.1 Voyage embedder

**Goal.** Wrap the Voyage API behind our `EmbeddingProvider` interface.

**Tasks.**
- `rag/embedder.py`: `class VoyageEmbedder(EmbeddingProvider)` with `async def embed_documents(texts: list[str]) -> list[list[float]]` and `embed_query(text: str) -> list[float]`
- Use model `voyage-3-lite`, output dim 512
- Batch up to 128 texts per call (Voyage allows up to 1000 but 128 is safe)
- Retry with backoff on rate limits
- `input_type` parameter: `"document"` for indexing, `"query"` for retrieval (Voyage distinguishes these)

**Definition of done.**
- A unit test embeds a sample list of 3 texts and gets back 3 vectors of length 512

### 8.2 Chunker

**Goal.** Split markdown docs into ~800-token chunks preserving structure where possible.

**Tasks.**
- `rag/chunker.py`: `def chunk_markdown(text: str, *, max_tokens: int = 800, overlap_tokens: int = 100) -> list[Chunk]`
- Strategy: parse markdown into sections by headers. If a section fits within max_tokens, emit as one chunk with `section_path` metadata. If it exceeds, fall back to recursive splitting (`["\n\n", "\n", ". ", " ", ""]`) with overlap.
- `Chunk` is a dataclass: `text: str`, `metadata: dict` (includes `section_path`, `chunk_index`)
- Approximate token count with `len(text) // 4` (Voyage's tokenizer is close to this ratio for English)

**Definition of done.**
- 6+ unit tests covering: short doc (1 chunk), long doc with headers (split by section), section exceeding limit (recursive split), overlap correctness
- `chunk_markdown(prd_text)` produces a sensible split of the PRD

### 8.3 Indexer

**Goal.** Pipeline: doc → chunks → embeddings → stored in pgvector.

**Tasks.**
- `rag/indexer.py`: `async def index_document(document_id: UUID) -> int` (returns number of chunks indexed)
- Reads document from DB, chunks it, embeds chunks in batches, writes to `document_chunks` with `embedding` populated
- `jobs/tasks/ingest_doc.py`: Arq task wrapping `index_document`
- `make ingest-docs` runs `index_document` on all 5 seed docs
- Idempotent: re-running deletes old chunks for that doc first

**Definition of done.**
- After `make ingest-docs`, `SELECT COUNT(*) FROM document_chunks` returns 30-80
- Each chunk has a non-null `embedding`
- Spot check: a chunk from PRD includes section_path like `"PRD > Performance"`

### 8.4 Retriever

**Goal.** Given a query string, return the top-K most relevant chunks.

**Tasks.**
- `rag/retriever.py`: `async def search_documents(query: str, *, project_id: UUID, document_kinds: list[str] | None = None, top_k: int = 5) -> list[ChunkResult]`
- Embeds the query (with `input_type="query"`)
- Runs SQL: `SELECT *, 1 - (embedding <=> $1) as similarity FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE project_id = $2 AND ($3::text[] IS NULL OR kind = ANY($3))) ORDER BY embedding <=> $1 LIMIT $4`
- Returns `ChunkResult` with `text`, `document_title`, `document_kind`, `section_path`, `similarity` (0..1)
- If max similarity < 0.4, log a warning (low-confidence retrieval)

**Definition of done.**
- `await search_documents("torque spec for chassis motor", project_id=...)` returns chunks from PRD with similarity > 0.5
- Filter `document_kinds=["eco_log"]` returns only ECO chunks
- A nonsense query returns chunks with low similarity, no crash

---

## 9. Phase 4 — Agent layer with 6 tools

### 9.1 Tool definitions

**Goal.** 6 typed tools registered with Anthropic's tool-use API.

**Tasks.**
- `agent/tools.py`: define each tool with Anthropic's tool schema format. Each tool has a name, description, JSON schema for inputs.
  1. `search_messages(query, channel?, author?, since?, topic?, limit=10)` — full-text search via `tsvector` plus filters
  2. `get_thread_context(message_id)` — returns the full thread
  3. `get_user_context(user_id)` — returns role, owned_subsystems, topic_weights
  4. `get_project_state(project_id)` — phase, milestones, phase_concerns
  5. `search_documents(query, document_kinds?, top_k=5)` — RAG search
  6. `query_decisions(query?, since?, status?)` — search the decision log
- Each tool has a Python handler function: `async def handle_search_messages(args: SearchMessagesArgs, ctx: ToolContext) -> ToolResult`
- `ToolContext` carries `db_session`, `current_user_id`, `current_project_id`
- Strict Pydantic input validation per tool

**Definition of done.**
- 6 tool definitions, 6 handlers, all type-checked
- Unit test for each handler: call with sample args, verify result shape

### 9.2 Agent runner

**Goal.** Multi-turn tool-use loop with bounded iterations.

**Tasks.**
- `agent/runner.py`: `async def run_agent(query: str, user_id: UUID, project_id: UUID) -> AsyncIterator[AgentEvent]`
- Implements the Anthropic tool-use loop: send messages with `tools=[...]`, if response has `tool_use`, run handler, append `tool_result` to messages, loop. Max 10 iterations.
- Yields `AgentEvent` objects: `TextDelta`, `ToolUseStart`, `ToolUseResult`, `Done`, `Error`
- System prompt in `agent/prompts/system.txt` (see sketch below)
- Structured error handling: if a tool throws, yield `ToolUseResult` with `is_error=True`, let the model recover

**System prompt sketch:**
```
You are EverCurrent, an AI assistant for a hardware engineering team building
"Warehouse Robot v2".

You help engineers understand what's happening across the project by reasoning
across team conversations, project documents, and tracked decisions.

When answering questions:
1. Use multiple tools when needed. A good answer often combines a doc lookup
   with a message search.
2. Always cite sources: [msg_142], [doc:PRD §3.2], [decision_5].
3. If information is in multiple places, look for connections and call them
   out explicitly.
4. If you are not confident, say so. Do not fabricate.
5. Be concise. Engineering teams hate fluff.

The current user is {user.name}, a {user.role}.
```

**Definition of done.**
- Calling `run_agent("what's the torque spec for the chassis motor?")` produces a stream that includes a `search_documents` tool call and a final answer with citation
- Calling `run_agent("what should I worry about this week?")` uses at least 2 different tools

### 9.3 SSE streaming endpoint

**Goal.** Frontend can subscribe to the agent stream.

**Tasks.**
- `api/routes/agent.py`: `POST /agent/chat` body `{query: str}`, returns `StreamingResponse` with `media_type="text/event-stream"`
- `agent/streaming.py`: serializer that turns `AgentEvent` into SSE-formatted strings (`event: text_delta\ndata: {"text": "..."}\n\n`)
- Heartbeat ping every 15s to prevent timeouts
- Honors `X-Impersonate-User` header to set the current user

**Definition of done.**
- `curl -N -X POST localhost:8000/agent/chat -d '{"query":"what is the torque spec?"}'` streams a series of SSE events including tool calls
- Connection closes cleanly with `event: done`

---

## 10. Phase 5 — Frontend dashboard and chat panel

### 10.1 App shell and impersonation

**Goal.** Layout, sidebar, user-switcher header.

**Tasks.**
- `app/layout.tsx` — global layout with sidebar, top bar, font setup
- `components/layout/Sidebar.tsx` — links to Dashboard, Timeline, Decisions
- `components/layout/ImpersonationDropdown.tsx` — shadcn Select listing 8 users
- `stores/impersonation.ts` — Zustand store: `{ currentUserId, setCurrentUserId }`, persisted to localStorage
- `lib/api.ts` — fetch wrapper that always sends `X-Impersonate-User: {currentUserId}`
- `app/page.tsx` redirects to `/dashboard`
- Install shadcn/ui base components: `button`, `card`, `select`, `dropdown-menu`, `dialog`, `input`, `textarea`, `scroll-area`, `separator`, `tabs`, `tooltip`, `skeleton`

**Definition of done.**
- Loading `localhost:3000/dashboard` shows the shell with the impersonation dropdown populated
- Switching the dropdown persists across reload

### 10.2 Digest dashboard view

**Goal.** Render the current user's digest with feedback controls.

**Tasks.**
- `app/dashboard/page.tsx` — server component fetches digest via `GET /digests/{currentUserId}?day={currentDay}`
- `components/digest/DigestCard.tsx` — renders the markdown digest using `react-markdown` (install) with a custom renderer for `[msg_XXX]` citations (turn them into hoverable tooltips showing the source message)
- `components/digest/FeedbackButtons.tsx` — thumbs up/down per item, POSTs to `/feedback`, optimistic update via TanStack Query
- `components/simulation/DaySwitcher.tsx` — dropdown to select day 1-5
- `components/simulation/PhaseSwitcher.tsx` — dropdown to switch project phase; calls `POST /projects/{id}/phase` then invalidates digest cache
- Loading skeletons, error boundaries

**Definition of done.**
- Dashboard shows Sarah's digest by default
- Switching user via dropdown re-fetches and re-renders
- Switching day re-fetches
- Switching phase triggers re-score on backend and refetches digest
- Thumbs up/down POSTs feedback successfully

### 10.3 Agent chat panel

**Goal.** Right-side chat with streaming responses and tool-call visibility.

**Tasks.**
- `components/chat/ChatPanel.tsx` — collapsible right-side panel, fixed width 400px
- `hooks/useAgent.ts` — manages SSE connection via `fetch` + `ReadableStream` (no EventSource since we need POST)
- `lib/stream.ts` — SSE parser turning the byte stream into typed events
- `components/chat/ChatMessage.tsx` — renders user message or assistant message with streaming text
- `components/chat/ToolCallView.tsx` — collapsible card showing tool name, args, and result preview
- Input box with send button (Cmd+Enter to send)
- Auto-scroll to bottom on new content

**Definition of done.**
- Typing a question and hitting send shows the assistant response streaming in
- Tool calls render as collapsible cards mid-stream
- Asking "what's the torque spec for the chassis motor?" shows a `search_documents` tool call and an answer with citation

### 10.4 E2E happy-path test

**Goal.** One Playwright test covering the core flow.

**Tasks.**
- `apps/web/e2e/dashboard.spec.ts`: impersonate Sarah → see her digest → click thumbs up on first item → verify the feedback was POSTed (mock or check via real API)
- Runs in CI

**Definition of done.**
- `pnpm playwright test` passes locally and in CI

---

## 11. Phase 6 — Multi-day simulation and timeline

### 11.1 Advance-day endpoint

**Goal.** Move the simulation forward one day.

**Tasks.**
- `api/routes/simulation.py`:
  - `POST /simulation/advance-day` — enqueues `advance_day` Arq task, returns 202 with job id
  - `GET /simulation/status` — returns current day, last advance timestamp
- `jobs/tasks/advance_day.py`: increments project's `current_day`, runs `enrich_day(new_day)` → `extract_decisions_for_day(new_day)` → `generate_all_digests(new_day)` in sequence
- Polling endpoint for the frontend to know when the job is complete

**Definition of done.**
- Starting from day 1, clicking advance produces day 2 digests after 30-60s
- Status endpoint reflects the new day

### 11.2 Advance button in UI

**Goal.** One-click day advance with progress indicator.

**Tasks.**
- `components/simulation/AdvanceDayButton.tsx` — button + loading state
- On click: POSTs, polls `/simulation/status` every 2s, shows a progress message ("Enriching messages... Generating digests..." — derive from Arq task hooks if possible, otherwise generic spinner)
- On completion: refetches all queries

**Definition of done.**
- Clicking advance updates the day in the UI within ~1 minute
- The new day's digest appears

### 11.3 Timeline view

**Goal.** Show how a user's digest evolved across 5 days.

**Tasks.**
- `app/timeline/page.tsx` — 5-column layout, each column is a day with the digest for the current user
- `api/routes/timeline.py`: `GET /timeline/{user_id}` returns array of 5 digest objects
- Visual treatment: top-of-digest items highlighted, days where the dominant topic shifted get a visual marker
- Optional: small "diff" indicator showing which items are new vs carried over

**Definition of done.**
- Timeline for Sarah visibly shows her digest evolving across days 1-5
- A reader can spot when a new topic became dominant

---

## 12. Phase 7 — Decision extraction

### 12.1 Decision schema and extractor

**Goal.** Extract structured decisions from messages.

**Tasks.**
- `decisions/schemas.py`: `ExtractedDecision` Pydantic model with `summary`, `rationale`, `decided_by`, `decided_at`, `source_message_ids`, `affected_subsystems`, `status`, `confidence`
- `decisions/extractor.py`: `async def extract_decisions(messages: list[Message], project: Project) -> list[ExtractedDecision]`
- Prompt asks Sonnet to identify decisions in a window of messages and emit structured JSON
- Filter low-confidence outputs (confidence < 0.6 drops to "proposed" status, < 0.4 is dropped)

**Prompt sketch:**
```
You analyze a window of Slack messages from a hardware engineering team to
identify decisions that were made.

A decision is when the team commits to a specific course of action: changing
a spec, approving an ECO, selecting a vendor, accepting a tradeoff, etc.

Messages:
{messages_json}

For each decision found, output:
- summary: one sentence ("Change motor M-2401 torque target from 10Nm to 12Nm")
- rationale: why ("To accommodate higher payload after thermal margin shrank")
- decided_by: user name or "team"
- decided_at: ISO timestamp of the message where decision was confirmed
- source_message_ids: array of message ids that contributed
- affected_subsystems: array (chassis, power, firmware, etc.)
- status: proposed | decided | implemented | reverted
- confidence: 0..1 (your confidence this is actually a decision)

If no decisions found, output [].

Output: JSON array.
```

**Definition of done.**
- `extract_decisions(day_3_messages, project)` returns at least 2-3 decisions for day 3
- Each decision cites real message IDs
- Confidence values are meaningful (high for clear decisions, low for "we should probably..." musings)

### 12.2 Decision extraction job

**Goal.** Run extractor as part of the day-advance flow.

**Tasks.**
- `jobs/tasks/extract_decisions.py`: `extract_decisions_for_day(day: int)` task
- Stores results in `decisions` table
- Wired into `advance_day` task between enrich and digest steps

**Definition of done.**
- After advancing through 5 days, the `decisions` table has 10+ decisions across the simulation

### 12.3 Decisions UI

**Goal.** Browseable decision log.

**Tasks.**
- `api/routes/decisions.py`:
  - `GET /decisions?project_id=&since=&status=` returns paginated decisions
- `app/decisions/page.tsx` — chronological list view
- `components/decisions/DecisionCard.tsx` — summary, rationale, who decided, affected subsystems, links to source messages
- Filters: by status, by subsystem

**Definition of done.**
- `/decisions` page lists all extracted decisions
- Clicking a source message link scrolls to or shows that message in a tooltip

---

## 13. Phase 8 — Eval harness

### 13.1 Eval infrastructure

**Goal.** Eval suite runs as part of pytest, outputs metrics tables.

**Tasks.**
- `tests/evals/conftest.py` — fixtures for loading eval data, setting up evaluator clients
- `tests/evals/_reporting.py` — table formatter for terminal output
- `make eval` runs `uv run pytest tests/evals/ -v -s --no-cov` (no cov for eval runs)

**Definition of done.**
- `make eval` runs and prints a header for each eval category, even with no evals yet

### 13.2 RAG retrieval eval

**Goal.** Measure retrieval precision and rank.

**Tasks.**
- `tests/evals/data/rag_qa.json`: 12-15 hand-labeled entries. Each is `{question, expected_document_kind, expected_keywords: [str], expected_section_path: str | null}`. Examples:
  - "What's the torque spec for the chassis motor?" → expected kind `prd`, keywords `["torque", "M-2401"]`
  - "What's the lead time on aluminum extrusion?" → expected kind `bom`, keywords `["aluminum", "extrusion"]`
  - "What ECOs were filed for the chassis?" → expected kind `eco_log`, keywords `["chassis"]`
- `tests/evals/test_rag_eval.py`: for each entry, run retrieval, compute:
  - **Precision@5**: 1.0 if a chunk from `expected_document_kind` appears in top 5, else 0.0
  - **Reciprocal Rank**: 1/(position of first matching chunk), 0 if not in top 10
  - **Keyword presence**: % of `expected_keywords` present in top-1 chunk text
- Aggregate: average precision@5, MRR (mean reciprocal rank), average keyword presence
- Output table

**Definition of done.**
- 12+ test cases pass through the eval
- Output shows P@5 and MRR averages
- Baseline numbers documented in `docs/EVAL_BASELINE.md` (target: P@5 ≥ 0.85, MRR ≥ 0.7)

### 13.3 Scoring engine eval

**Goal.** Verify scoring produces sensible per-user rankings.

**Tasks.**
- `tests/evals/data/scoring_scenarios.json`: 6-8 scenarios. Each has a set of enriched messages, a user, project state, and `expected_top_3_message_ids`. Scenarios designed to exercise different aspects:
  - Pure role match
  - Cross-functional dependency triggering
  - Phase weight shift (same messages, DVT vs PVT, different top 3)
  - Personal feedback weight overrides
- `tests/evals/test_scoring_eval.py`: for each scenario, score and check that all expected IDs are in actual top 3
- Output table: scenario name | pass/fail | actual top 3 IDs

**Definition of done.**
- All 6+ scenarios pass
- Output table shows each scenario's result

### 13.4 Digest quality eval (LLM-as-judge)

**Goal.** Use Sonnet to score generated digests against a rubric.

**Tasks.**
- `tests/evals/data/digest_rubric.json`: rubric with 4 dimensions, each scored 1-5:
  - Personalization: matches user's role and concerns
  - Prioritization: most urgent item first
  - Actionability: tells the user what to do next
  - Citation accuracy: every cited msg_id exists in the source set
- `tests/evals/test_digest_eval.py`: generate digests for 3-5 personas on a known day, then call Sonnet with the rubric to score each digest. Sonnet outputs scores + brief justifications.
- Citation accuracy is also checked programmatically (parse `[msg_XXX]` references, check each exists)
- Output: average score per dimension across personas

**Definition of done.**
- Eval runs and outputs a 4-dimension score table
- Citation accuracy is computed programmatically AND scored by the judge
- Baseline: target average ≥ 4.0/5 on each dimension

### 13.5 Decision extraction eval

**Goal.** Measure decision extractor recall and field accuracy.

**Tasks.**
- `tests/evals/data/decision_truth.json`: hand-labeled ground truth for ~10 message windows. Each entry: `{message_ids: [...], expected_decisions: [{summary_keywords, decided_by, affected_subsystems}]}`
- `tests/evals/test_decision_eval.py`: for each window, run extractor, then for each ground truth decision check if any extracted decision matches (keyword presence in summary + affected_subsystem overlap). Compute:
  - **Recall**: matched / total ground truth
  - **Field accuracy**: for matched decisions, % of fields correct (`decided_by` exact match, `affected_subsystems` Jaccard ≥ 0.5)
  - **Hallucination rate**: extracted decisions with no ground-truth match / total extracted
- Output: recall, field accuracy, hallucination rate

**Definition of done.**
- Eval runs and outputs the 3 metrics
- Baseline: recall ≥ 0.7, field accuracy ≥ 0.8, hallucination ≤ 0.2

### 13.6 Eval baseline document

**Goal.** Capture what "good" looks like for this project.

**Tasks.**
- `docs/EVAL_BASELINE.md` with:
  - Baseline numbers for each eval (after running on the committed seed data)
  - Notes on what would trigger investigation (regressions > 10%)
  - Pointers to which prompt or component to inspect when a metric drops

**Definition of done.**
- `EVAL_BASELINE.md` exists with current numbers
- README links to it

---

## 14. Phase 9 — Production polish

### 14.1 Docker production builds

**Goal.** Production-quality multi-stage Dockerfiles.

**Tasks.**
- `apps/api/Dockerfile`: stage 1 (`builder`) installs uv + project deps in a venv. Stage 2 (`runtime`) is slim Python 3.13, copies venv, runs as non-root, uses tini for signal handling, defines healthcheck. Distroless if feasible, else slim.
- `apps/web/Dockerfile`: stage 1 (`builder`) runs `pnpm install --frozen-lockfile` and `pnpm build` with `output: 'standalone'` in `next.config.ts`. Stage 2 (`runtime`) is Node 22 alpine, copies `.next/standalone` + `.next/static` + `public`, runs `node server.js`, non-root user.
- Both images < 300 MB
- Built images run cleanly via `docker compose up`

**Definition of done.**
- `docker compose build` produces both images
- `docker compose up` starts everything, full app works
- Image sizes meet target

### 14.2 Observability hooks (wired, not shipped)

**Goal.** Logs and traces ready to be shipped to a collector.

**Tasks.**
- Structlog configured with JSON output, request ID context, log level from env
- OpenTelemetry SDK initialized, FastAPI instrumented, exporter set to OTLP but defaults to a noop in local dev
- Custom span attributes on key operations: `evercurrent.scoring.duration_ms`, `evercurrent.llm.model`, `evercurrent.llm.tokens_in`, `evercurrent.llm.tokens_out`, `evercurrent.rag.similarity_max`
- `/metrics` endpoint stub for Prometheus (not implemented in detail, just hooked)

**Definition of done.**
- API logs are valid JSON with request_id
- A request through the API generates spans (visible if OTLP_ENDPOINT is set; harmless if not)

### 14.3 Documentation

**Goal.** Reviewer can understand the system from docs alone.

**Tasks.**

`docs/ARCHITECTURE.md`:
- System overview diagram (Mermaid)
- Layer boundaries (routes/services/repositories/db)
- Module responsibilities
- Data flow: ingestion → enrichment → scoring → digest, plus the agent flow
- Design decisions with rationale (why Arq not Celery, why Voyage not OpenAI, why Haiku for tagging, why model tiering, why server components by default)

`docs/CONTRIBUTING.md`:
- Conventional commits
- Branch naming
- Pre-commit setup
- How to run tests, lint, eval
- How to add a new module

`docs/PRODUCTION_ROADMAP.md`:
- What's in scope today
- Real Slack/Teams integration (adapter slot, OAuth, webhooks, rate limiting, idempotency, retry semantics)
- Behavioral signals (reactions, reply patterns, mention tracking)
- Multi-tenancy and auth (SSO, RBAC, tenant isolation, audit logs)
- Observability (OTel → Grafana Cloud, LLM-specific metrics, retrieval recall trending)
- Scaling considerations (when to add Temporal, when to graduate Voyage to fine-tuned embeddings, sharding)
- RAG evolution (structural chunking, hybrid search + BM25 + RRF, cross-encoder re-ranking, query expansion via HyDE, eval set growth)
- ML/personalization roadmap (rule-based → learned ranking, A/B testing, online learning)
- Cost optimization (caching, batching, tiering)
- Compliance and security (ITAR, SOC 2)
- AWS deployment story: ECS Fargate for api + worker + web, RDS Postgres with pgvector parameter group, ElastiCache Redis, S3 for doc uploads, CloudFront for web, Secrets Manager for API keys, ALB for routing. High-level diagram in Mermaid.
- Reliability (chaos testing, degraded-mode, idempotency keys)

`docs/LEARNING_NOTES.md`:
- Template sections to fill as you build: embeddings, chunking tradeoffs, tool-use patterns, decision extraction failure modes, eval insights

`docs/DEMO_SCRIPT.md`:
- The 5-minute walkthrough (see §16)

**Definition of done.**
- All 5 docs exist, none are stubs
- ARCHITECTURE.md has a real Mermaid diagram
- PRODUCTION_ROADMAP.md has at least 2 paragraphs per major section

### 14.4 Top-level README

**Goal.** Strong first impression.

**Tasks.**
- One-paragraph elevator pitch at the top
- Demo GIF or screenshot (record one once the app works end-to-end)
- 30-second "how to run" section
- Architecture diagram (link to ARCHITECTURE.md for detail)
- Feature list with checkmarks
- Eval results summary table (paste from EVAL_BASELINE.md)
- Links to deeper docs

**Definition of done.**
- README opens with the pitch and a demo visual
- A reviewer who reads only the README understands what the project is

### 14.5 Final pass

**Goal.** Polish before submission.

**Tasks.**
- Run `make lint` and fix all warnings
- Run `make test` and fix all failures
- Run `make eval` and verify baseline metrics
- Record a 2-3 minute demo video (Loom or local screen recording)
- Tag a `v0.1.0` release
- Write a submission email/cover note pointing at the repo, the demo video, the README, and PRODUCTION_ROADMAP.md as the 3 things to look at first

**Definition of done.**
- All lint, type, test, eval passes
- Demo video recorded
- README is the polished first thing a reviewer sees

---

## 15. Whole-project definition of done

A reviewer should be able to:

1. Clone the repo
2. Set 2 env vars (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`) in `.env`
3. Run `make up` and have everything working in under 2 minutes
4. Open `http://localhost:3000`, switch between users via the dropdown, see meaningfully different digests
5. Switch project phase from DVT to PVT and see digests reshuffle
6. Click thumbs up on an item and see user weights update (refresh shows the change in ranking)
7. Click "advance day" and watch the next day's digest generate
8. Open the chat panel, ask "what's the torque spec for the chassis motor?", and see the agent retrieve docs and answer with citation
9. Open the timeline view and see how Sarah's digest evolved across 5 days
10. Open the decisions page and see structured decisions extracted from messages
11. Run `make eval` and see the eval table
12. Read PRODUCTION_ROADMAP.md and understand the path from take-home to product

If all 12 work, ship it.

---

## 16. Demo script (the 5-minute walkthrough)

Goes in `docs/DEMO_SCRIPT.md`.

**Minute 1 — The framing.** "Hardware engineering teams have knowledge scattered across Slack, MCAD, Jira, Confluence. A mech engineer doesn't read the supply chain channel, but when a supplier strike happens to the aluminum extrusion her bracket needs, she needs to know today. EverCurrent's positioning is cross-functional dependency tracking and decision extraction. I built this to demonstrate both."

**Minute 2 — The personalization demo.** Open the dashboard as Sarah (mech). Her digest leads with the bracket ECO, the thermal failure, and a cross-functional mention of the extrusion delay (which she would never have caught in #supply-chain). Switch impersonation to Mei (supply chain). Her digest leads with the extrusion disaster. Same underlying messages, different digests, driven by role + dependency match.

**Minute 3 — The phase awareness.** Change project phase from DVT to PVT via the dropdown. Watch Sarah's digest reshuffle toward production yield concerns. This is governed by `phase_concerns` config and the scoring engine, not by re-asking an LLM. Predictable, cheap, testable. Senior architecture move.

**Minute 4 — The agentic chat.** Open the chat panel. Ask "what should I worry about this week?" Watch it call `get_user_context`, `search_messages`, `query_decisions`, then synthesize. Then ask "what's the torque spec for the chassis motor?" Watch it call `search_documents` and return with citation. Highlight the multi-source reasoning the agent does.

**Minute 5 — Eval harness and production story.** Run `make eval` live, show the table. Explain why this matters: every AI feature should be measurable. Point at PRODUCTION_ROADMAP.md, walk through the top 3 sections (real Slack adapter, ITAR/SOC 2 compliance, observability) in 30 seconds each. Close with "the architecture decouples ingestion, enrichment, scoring, retrieval, and agent reasoning into independently testable services. Each layer can scale or be swapped without touching the others."

---

## Notes for execution

- **Use Claude Code phase-by-phase, subphase-by-subphase.** Start each session with: "We're implementing Phase N.M of the build doc. Read the doc, then implement just N.M. Stop at its definition of done so I can verify."
- **Commit at every subphase.** One commit per subphase with conventional commit message: `feat(phase-2.3): scoring engine and weights`.
- **Run `make lint` and `make test` after every subphase.** Don't accumulate broken state.
- **The LEARNING_NOTES.md is for you.** Fill it as you build. The Voyage chunking behavior, the agent's tool-call patterns, the times it called the wrong tool. Write it down. You will use it in interview answers later.
- **Do not skip the eval harness.** Half the interview signal is in eval rigor. Cut Phase 6 or Phase 7 before cutting Phase 8.
- **Record the demo video before you think you're done.** Recording always reveals one more bug.

Ship it, bossman.
