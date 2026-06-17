# AGENTS.md

Source of truth for working in this repo. Loaded into every Claude Code session
via `CLAUDE.md`; also read by other coding agents (Codex, Copilot). Wins for
code-style decisions.

`docs/ARCHITECTURE.md` covers backend architecture + rationale. The build is
complete; the code is the source of truth.

**Code conventions are split by app and auto-load with the matching subtree:**

- `apps/api/AGENTS.md` — Python, SQL/DB, LLM/prompts (backend).
- `apps/web/AGENTS.md` — React/Next/TanStack conventions + the Next.js
  breaking-change warning (read before writing web code; installed
  Next 16.2 / React 19 / Tailwind v4 differ from training data).

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
  dependency-injector. ruff (lint+format), ty (types). Observability: Prometheus
  metrics (`/metrics`) + Loki logs via Grafana — no distributed tracing.
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
│   │   │   ├── db/                   ORM models (tables) + repositories
│   │   │   ├── classification/       Message classification (Haiku)
│   │   │   ├── scoring/              Per-user relevance scoring (pure)
│   │   │   ├── digest/               Per-member digest generation
│   │   │   ├── cards/                Decision cards (decision extraction)
│   │   │   ├── insights/             Eve, the tool-using insight agent
│   │   │   ├── agent_tools/          Eve's in-process tool implementations
│   │   │   ├── rag/                  Embeddings, chunking, retrieval
│   │   │   ├── connectors/           Slack/Dropbox ingestion connectors
│   │   │   ├── ingestion/            Document ingestion + doc classification
│   │   │   ├── timeline/             Per-member timeline projection
│   │   │   ├── tenancy/              RLS org-context helpers
│   │   │   ├── auth/                 Auth0/JWT request deps
│   │   │   ├── jobs/                 Celery tasks (`celery_tasks.py`) + beat
│   │   │   ├── api/                  FastAPI routers + shared HTTP schemas
│   │   │   └── llm/                  Anthropic client wrapper + tiering
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
- **Two data shapes, one rule.** A **model** is a SQLAlchemy class = one
  database table; it lives only in `db/models/`. A **schema** is a Pydantic
  class = a data shape (HTTP request/response, LLM I/O, or a repository
  read-model); it lives wherever it is used. *Is it a table? → model. Anything
  else Pydantic? → schema.* There is no separate "domain" layer.
- **Repositories** are the only place SQL runs; they take an `AsyncSession`,
  query tables (models), and **return schemas** — never ORM models. Shared
  read-models live next to their repository (`api/` may depend on `db/`, never
  the reverse).
- **Dependency injection** for side-effecting collaborators (DB, Anthropic,
  embedder, Redis) via `Depends()` or the container. No globals.
- **Adapter pattern** for external services: `EmbeddingProvider`/`VoyageEmbedder`,
  `LLMProvider`/`AnthropicProvider`. Swappable.
- **Feature slices.** `classification/`, `scoring/`, `digest/`, `cards/`,
  `insights/`, `rag/` each own their schemas + logic; the shared tables they
  read stay central in `db/models/`.

## 5. Git workflow

- Conventional Commits: `feat:`/`fix:`/`refactor:`/`chore:`/`docs:`. Scope =
  phase. Atomic, one per subphase. Branches: `feat/phase-N.M-short-description`.
- Never `--no-verify`. Attribution empty (`.claude/settings.json`) — no
  `Co-Authored-By`.
- Per task: restate goal + files, wait for `go`, implement only what's asked,
  `make lint`, verify, commit, stop. Don't expand scope — ask if ambiguous.

## 6. Testing

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

## 7. Honest disagreement

If a standard here is wrong for a specific case, say so. Don't silently violate
it, don't follow it into a broken design. Defaults, not laws.
</content>
</invoke>
