# AGENTS.md

This is the source of truth for working in this repository. It is loaded into
every Claude Code session via `CLAUDE.md`, and is also the file other coding
agents (Codex, Copilot, etc.) read.

## 1. Project

**EverCurrent** is an agentic AI layer for hardware engineering teams. It
personalizes information by role, project phase, and behavior. It tracks
cross-functional dependencies. It extracts structured decisions from team
chatter. It answers questions by reasoning across team docs and conversations.

This is a take-home project demonstrating production-grade engineering for the
EverCurrent team.

## 2. Authoritative documents

- `EVERCURRENT_BUILD_DOC.md` — the full build plan with phases and subphases.
  This is the work list.
- `docs/ARCHITECTURE.md` — design decisions and rationale.
- `docs/PRODUCTION_ROADMAP.md` — the scale-out story.
- `AGENTS.md` (this file) — coding standards and conventions.

If anything in this file conflicts with the build doc, the build doc wins for
scope. This file wins for code-style decisions.

## 3. Tech stack (locked, May 2026)

### Backend

- Python 3.13 with uv
- FastAPI 0.136.1, Pydantic 2.12+, SQLAlchemy 2.0 async, Alembic
- Postgres 17 with pgvector 0.8+
- Arq job queue on Redis 8.x (latest stable)
- Anthropic SDK with Claude Sonnet 4.6 (`claude-sonnet-4-6`) and Haiku 4.5
  (`claude-haiku-4-5-20251001`)
- Voyage AI (`voyage-3-lite`, 512 dims) for embeddings
- structlog, OpenTelemetry SDK, dependency-injector
- ruff (lint + format), ty (type check)

### Frontend

- Node 25.x (latest stable), pnpm 11+
- Next.js 16.2 App Router, React 19, TypeScript 5 strict
- Tailwind v4, shadcn/ui, Lucide icons
- TanStack Query v5, Zustand for client state (sparingly)
- Zod at every external boundary
- ESLint strict, Prettier

### Infra (local only)

- Docker + docker-compose for local dev
- GitHub Actions for CI

## 4. Repository layout

```
evercurrent/
├── apps/
│   ├── api/                          Python FastAPI backend
│   │   ├── src/evercurrent/
│   │   │   ├── domain/               Pure domain models, no I/O
│   │   │   ├── db/                   SQLAlchemy models, repositories
│   │   │   ├── ingestion/            Synthetic data generation
│   │   │   ├── enrichment/           Message tagging
│   │   │   ├── scoring/              Per-user relevance scoring
│   │   │   ├── digest/               Digest generation
│   │   │   ├── decisions/            Decision extraction
│   │   │   ├── rag/                  Embeddings, chunking, retrieval
│   │   │   ├── agent/                Tool-using agent
│   │   │   ├── jobs/                 Arq tasks
│   │   │   ├── api/                  FastAPI routers
│   │   │   └── llm/                  Anthropic client wrapper
│   │   ├── tests/evals/              Eval harness (NOT unit tests)
│   │   ├── alembic/versions/
│   │   ├── seed_data/                Committed synthetic data
│   │   └── pyproject.toml
│   └── web/
│       ├── app/                      Next.js App Router pages
│       ├── components/
│       ├── lib/, hooks/, stores/
│       └── package.json
├── docs/
└── EVERCURRENT_BUILD_DOC.md
```

## 5. Architecture principles

- **Layered.** Routes → services → repositories → database. No SQL in routes.
  No HTTP concerns in services. No business logic in repositories.
- **Pure domain models** in `domain/` with zero I/O dependencies. SQLAlchemy
  models in `db/` map to/from domain models.
- **Dependency injection.** Side-effecting collaborators (DB session,
  Anthropic client, embedder, Redis) are injected via FastAPI `Depends()` or
  the `dependency-injector` container. No globals.
- **Adapter pattern for external services.** `EmbeddingProvider` interface
  with `VoyageEmbedder` implementation. `LLMProvider` interface with
  `AnthropicProvider` implementation. Swappable.
- **Self-contained service modules.** `enrichment/`, `scoring/`, `digest/`,
  `decisions/`, `rag/`, `agent/` each own their domain end-to-end.

## 6. Python coding standards

- Type hints on every function signature and return type. No exceptions.
- No `Any` except where genuinely dynamic, with `# type: ignore[...]` and
  a comment explaining why.
- Pydantic v2 strict mode on all schemas:
  `model_config = ConfigDict(strict=True)`.
- Async/await for all I/O (database, Anthropic, Voyage, Redis, HTTP).
- `asyncio.TaskGroup` for structured concurrency. No orphaned tasks.
- Connection pool management via FastAPI lifespan events.
- **structlog** for all logging with JSON output. Never `print()`, never
  bare `logging`.
- Request ID propagation through logs via middleware.
- Graceful shutdown handlers for SIGTERM in API and worker.
- `ruff check` and `ty check` must pass clean before commit.
- `pyproject.toml` is the single source of truth. No `setup.py`, no
  `requirements.txt`, no `setup.cfg`.
- Function bodies under 50 lines. Files under 400 lines. Both are smells if
  exceeded — refactor.
- Prefer composition over inheritance.

## 7. TypeScript coding standards

- `strict: true` in tsconfig.
- No `any`. Use `unknown` and narrow.
- Zod schemas validate every external boundary (API responses, form input,
  localStorage reads).
- Server components by default in Next.js. Add `"use client"` only when
  interactivity demands it.
- TanStack Query for all server state. No `useEffect` for data fetching.
- Zustand for client state only when component-local state is insufficient.
- Tailwind only. No CSS-in-JS. No inline styles except where dynamic values
  require it.
- Lucide icons via shadcn. No emojis in code.
- File names: `kebab-case.tsx` for files, `PascalCase` for component names.
- Hooks start with `use`, exported from `apps/web/hooks/`.

## 8. SQL and database conventions

- All DDL goes through Alembic migrations. Never edit a migration after it
  has been merged.
- Use snake_case for table and column names.
- Every table has `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` unless
  there is a domain-specific natural key.
- Timestamps are `timestamptz`, not `timestamp`. Default to `now()`.
- Foreign keys always have `ON DELETE` behavior specified.
- Indexes are deliberate. Comment in the migration explains the query they
  serve.
- pgvector columns use `vector(512)` for `voyage-3-lite`. HNSW index for
  ANN search.

## 9. LLM and prompt conventions

- All LLM calls go through `src/evercurrent/llm/client.py`. No raw
  `anthropic.AsyncAnthropic()` elsewhere.
- Model selection via `llm/tiering.py`:
  - `tag()` → Haiku (`claude-haiku-4-5-20251001`)
  - `generate_digest()`, `extract_decisions()`, `chat_with_tools()` → Sonnet
    (`claude-sonnet-4-6`)
- Prompts live in `<module>/prompts/<name>.txt`, NOT inline in Python code.
- Prompt outputs are parsed via Pydantic models in `<module>/schemas.py`.
- Retry transient errors with exponential backoff via tenacity.
- Log every LLM call with: model name, input token count, output token
  count, latency.

## 10. Git workflow

- Conventional Commits: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`.
- Scope is the phase: `feat(phase-2.3): scoring engine and weights`.
- One commit per subphase. Atomic.
- Branch names: `feat/phase-N.M-short-description`.
- Never `git commit --no-verify`. Pre-commit hooks are there for a reason.
- Attribution is empty (see `.claude/settings.json`). No `Co-Authored-By`.

## 11. Testing philosophy

We do NOT write traditional unit/integration tests across the codebase.
Reasoning: it is a take-home with a small scope and high engineering bar
elsewhere, and the eval harness covers the AI-quality dimension which is
the harder thing to measure.

The only test code we write:

- An eval harness in `apps/api/tests/evals/` covering four dimensions:
  - RAG retrieval: precision@5 and MRR on hand-labeled question/source pairs
  - Scoring engine: scenario-based ranking checks
  - Digest quality: LLM-as-judge with a rubric
  - Decision extraction: recall and field accuracy
- Unit tests for the `/health` and `/ready` endpoints, living at
  `apps/api/tests/unit/test_health.py` and
  `apps/api/tests/unit/test_ready.py`. These prove the service boots and
  its dependencies (DB, Redis) are reachable. Nothing else goes in
  `tests/unit/`.

Any test code outside those two paths is out of scope. If a subphase in
the build doc lists tests beyond these (e.g. "unit tests on scoring
engine", "integration test on end-to-end pipeline", "vitest unit tests"),
treat that as superseded by this section — skip those tasks and note it
in the subphase commit message.

Evals are runnable via `make eval`. They are NOT in CI gates by default;
they are reference numbers documented in `docs/EVAL_BASELINE.md`. The
health/ready unit tests run via `make test` and ARE in CI.

## 12. Subphase workflow

Every piece of work corresponds to a subphase in `EVERCURRENT_BUILD_DOC.md`.
Workflow:

1. Read the subphase: goal, tasks, definition of done.
2. Restate the goal in one sentence and list the files to be touched.
3. Wait for `go` from the user.
4. Implement only what the subphase asks for.
5. Run `make lint` after implementation.
6. Verify the subphase's definition of done.
7. Commit with `feat(phase-N.M): description`.
8. Stop. Do not auto-start the next subphase.

If you find yourself doing something not listed in the subphase, stop and
ask. Scope creep is the most common failure mode.

## 13. Documentation

- Every module has a module-level docstring explaining its role.
- Every non-obvious public function has arg/return docs.
- Every top-level directory has a README.md.
- `docs/ARCHITECTURE.md` records design decisions with rationale.
- `docs/LEARNING_NOTES.md` is the engineer's personal log — observations
  about embedding behavior, tool-use patterns, eval insights. Filled as
  the project progresses, not at the end.

## 14. Honest disagreement

If you (Claude) think a coding standard in this file is wrong for a
specific case, say so. Don't silently violate it, and don't blindly follow
it into a broken design. The standards are defaults, not laws.
