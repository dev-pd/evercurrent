# AGENTS.md

Source of truth for working in this repo. Loaded into every Claude Code session
via `CLAUDE.md`; also read by other coding agents (Codex, Copilot). Wins for
code-style decisions.

`docs/ARCHITECTURE.md` covers backend architecture + rationale. The build is
complete; the code is the source of truth. `apps/web/AGENTS.md` carries the
Next.js breaking-change warning — **read it before writing web code; the
installed Next 16.2 / React 19 / Tailwind v4 APIs differ from training data.**

## 1. Project

**EverCurrent** — agentic AI layer for hardware engineering teams. Personalizes
info by role/phase/behavior, tracks cross-functional dependencies, extracts
structured decisions from chatter, answers questions by reasoning across team
docs and conversations. Take-home demonstrating production-grade engineering.

## 2. Tech stack (locked, May 2026)

- **Backend:** Python 3.13 (uv), FastAPI 0.136.1, Pydantic 2.12+, SQLAlchemy 2.0
  async, Alembic, Postgres 17 + pgvector 0.8+, Celery 5.4 (Redis broker/backend)
  + Beat, Anthropic SDK (Sonnet 4.6 `claude-sonnet-4-6`, Haiku 4.5
  `claude-haiku-4-5-20251001`), Voyage `voyage-3-lite` (512d), structlog,
  OpenTelemetry, dependency-injector. ruff (lint+format), ty (types).
- **Frontend:** Node 25.x, pnpm 11+, Next.js 16.2 App Router, React 19, TS 5
  strict, Tailwind v4, shadcn/ui, Lucide, TanStack Query v5, Zustand (sparingly),
  Zod at boundaries. ESLint, Prettier.
- **Infra (local):** Docker compose, GitHub Actions CI.

Locked versions are deliberate. Don't add dependencies without asking.

## 3. Repository layout

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
│   │   │   ├── jobs/                 Celery tasks (`celery_tasks.py`) + cron via beat
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
└── docs/
```

## 4. Architecture principles

- **Layered.** Routes → services → repositories → DB. No SQL in routes, no HTTP
  concerns in services, no business logic in repositories.
- **Pure domain models** in `domain/` (zero I/O); `db/` SQLAlchemy models map
  to/from them.
- **Dependency injection** for side-effecting collaborators (DB, Anthropic,
  embedder, Redis) via `Depends()` or the container. No globals.
- **Adapter pattern** for external services: `EmbeddingProvider`/`VoyageEmbedder`,
  `LLMProvider`/`AnthropicProvider`. Swappable.
- **Self-contained service modules:** `enrichment/`, `scoring/`, `digest/`,
  `decisions/`, `rag/`, `agent/` each own their domain end-to-end.

## 5. Code conventions (non-obvious — defaults differ)

These are project calls I would otherwise get wrong; the rest (type hints,
`strict`, async I/O, no `import *`) is assumed.

**Python (`apps/api`)**

- Logging is **structlog only** — never `print()`, never bare `logging`.
- No raw `anthropic.AsyncAnthropic()` — all LLM calls go through
  `src/evercurrent/llm/client.py`.
- Repositories return **domain models**, never SQLAlchemy models. Repos take an
  `AsyncSession` param; they don't create their own.
- Pydantic v2 `model_config = ConfigDict(strict=True)` on every schema.
- FastAPI collaborators via `Depends(get_x)` factories — no module globals.
- Celery tasks in `jobs/tasks/<name>.py`, registered in `celery_tasks.py`, and
  **idempotent** (replay-safe via unique constraints / upserts).
- No docstrings/inline comments by default; never strip functional directives
  (`# noqa`, `# type: ignore`, `# ruff:`, shebangs).
- Smells: function >50 lines, file >400 lines.

**Web (`apps/web`)**

- **No `useEffect` for data fetching** — TanStack Query for all server state
  (one `useQuery` per resource, tuple keys, explicit invalidation).
- Zod validates **every** external boundary (API responses, forms,
  localStorage, non-trivial URL params).
- Server components by default; `"use client"` only when interactivity demands.
- Zustand for cross-component client state, sparingly. No Redux/MobX/Recoil/Jotai.
- No `any` (use `unknown` + narrow). No `as` assertions unless unavoidable.
- Naming: `kebab-case.tsx` files, `PascalCase` components, `use-camel-case.ts`
  hooks, lowercase Zod schemas. Named exports except page components.
- SSE: parser in `lib/stream.ts`, consumed via the `useAgent` hook.
- Tailwind only (`cn()` helper for conditionals). Lucide via shadcn, no emojis.
- Smells: component >200 lines, file >300 lines.

## 6. SQL & database

- All DDL via Alembic. Never edit a merged migration.
- snake_case names. `timestamptz` not `timestamp`, default `now()`.
- Every table: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` unless a natural key.
- FKs always specify `ON DELETE`. Indexes deliberate, commented with the query
  they serve.
- pgvector: `vector(512)` for `voyage-3-lite`, HNSW index for ANN.

## 7. LLM & prompts

- All LLM calls go through `src/evercurrent/llm/client.py`. No raw
  `anthropic.AsyncAnthropic()` elsewhere.
- Model tiering in `llm/tiering.py`: `tag()` → Haiku; `generate_digest()`,
  `extract_decisions()`, `chat_with_tools()` → Sonnet.
- Prompts in `<module>/prompts/<name>.txt`, never inline. Outputs parsed via
  Pydantic in `<module>/schemas.py`.
- Retry transient errors with tenacity backoff. Log every call: model, in/out
  tokens, latency.

## 8. Git workflow

- Conventional Commits: `feat:`/`fix:`/`refactor:`/`chore:`/`docs:`. Scope =
  phase. Atomic, one per subphase. Branches: `feat/phase-N.M-short-description`.
- Never `--no-verify`. Attribution empty (`.claude/settings.json`) — no
  `Co-Authored-By`.
- Per task: restate goal + files, wait for `go`, implement only what's asked,
  `make lint`, verify, commit, stop. Don't expand scope — ask if ambiguous.

## 9. Testing

TDD on deterministic code, evals on LLM behaviour.

| Kind | Location | Runner | When |
|------|----------|--------|------|
| Unit (Python) | `apps/api/tests/unit/` | pytest + asyncio | pre-commit, CI, `make test` |
| Integration | `apps/api/tests/integration/` | pytest + testcontainers | CI, `make test` |
| Eval (LLM) | `apps/api/tests/evals/` | custom runner | `make eval`, not CI gate |
| Unit (TS) | `apps/web/__tests__/` | vitest + RTL + msw | pre-commit, CI |
| E2E | `apps/web/e2e/` | Playwright | CI, `make e2e` |

- New deterministic modules: red → green → refactor. Test public behaviour, not
  privates. Name tests as full sentences.
- Coverage gate 80% on `auth/`, `tenancy/`, `scoring/`, `cards/`, `ingestion/`,
  `db/repositories/`, `connectors/*/events`. Agents + prompts excluded.
- Do NOT unit-test: prompt strings, LLM content, generated SQL (test real DB via
  testcontainers), thin SDK wrappers.

## 10. Honest disagreement

If a standard here is wrong for a specific case, say so. Don't silently violate
it, don't follow it into a broken design. Defaults, not laws.
</content>
</invoke>
