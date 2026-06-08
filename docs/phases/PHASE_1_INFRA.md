# Phase 1 — Infra

## Goal

Get a one-command local dev loop working: `make up` brings every
service alive, `make test` runs the test suite (placeholder green),
`make lint` enforces style, pre-commit blocks bad commits, GitHub
Actions runs the same checks on push. ngrok integration is wired
so Slack/Drive webhooks reach our local API.

By the end of this phase you can write your first failing test
and watch it run — TDD is unblocked from here on.

## Why this phase, this order

Every other phase writes code. This phase makes writing code
safe: the test harness exists, the lint guard exists, the local
services exist. Skipping this and "we'll add tests later" is how
take-homes turn into 4am death marches.

The order inside this phase matters too: pyproject + package.json
first (deps available), docker-compose second (services up),
pre-commit + Makefile third (workflow), CI last (mirrors local).

## Pre-requisites

- Phase 0 done (clean baseline)

## Files touched

### New
- `Makefile` — `make up`, `make down`, `make test`, `make lint`, `make eval`, `make ngrok`
- `docker-compose.yml` — postgres + redis + api + worker + beat + web
- `apps/api/Dockerfile.dev` — Python 3.13 + uv + hot reload
- `apps/web/Dockerfile.dev` — Node 25 + pnpm + hot reload
- `.env.example` — every env var the stack reads, with safe defaults
- `.pre-commit-config.yaml` — ruff, ty, eslint, prettier hooks
- `.github/workflows/ci.yml` — lint + typecheck + test on push/PR
- `apps/api/tests/conftest.py` — testcontainers Postgres + Redis fixtures
- `apps/api/tests/integration/__init__.py`
- `apps/web/vitest.config.ts`
- `apps/web/playwright.config.ts`
- `apps/web/__tests__/setup.ts`
- `docs/DEV_SETUP.md` — first-time setup instructions

### Modified
- `apps/api/pyproject.toml` — add: pytest, pytest-asyncio, pytest-cov, polyfactory, testcontainers, httpx
- `apps/web/package.json` — add: vitest, @testing-library/react, @testing-library/jest-dom, msw, @playwright/test, husky, lint-staged

### Deleted
- nothing new — Phase 0 already cleaned house

## Tasks

1. **`pyproject.toml` deps.** Add dev group: `pytest`, `pytest-asyncio`, `pytest-cov`, `polyfactory`, `testcontainers[postgres,redis]`, `httpx`. `uv lock` + `uv sync --dev`.
2. **`package.json` deps.** Add devDeps: `vitest`, `@vitest/ui`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `msw`, `@playwright/test`, `husky`, `lint-staged`. `pnpm install`.
3. **`docker-compose.yml`** — services:
   - `postgres`: postgres:17 + pgvector extension via init.sql
   - `redis`: redis:7-alpine
   - `api`: build apps/api, depends_on postgres+redis, mounts source for hot reload, exposes 8000
   - `worker`: same image as api, runs `celery -A evercurrent.jobs.celery_app worker`
   - `beat`: same image, runs `celery -A evercurrent.jobs.celery_app beat`
   - `web`: build apps/web, exposes 3000, mounts source
   - Named volume for postgres data
4. **Init pgvector.** `postgres/init.sql` runs `CREATE EXTENSION IF NOT EXISTS vector;` on first boot.
5. **`Makefile` targets** — `up`, `down`, `logs`, `lint`, `format`, `test`, `test-unit`, `test-integration`, `e2e`, `eval`, `migrate`, `shell`, `ngrok` (runs `ngrok http 8000` and prints URL).
6. **Pre-commit config.** Ruff format → ruff check → ty → eslint → prettier → run-pytest-changed. Install with `pre-commit install`.
7. **`apps/api/tests/conftest.py`** — pytest fixtures:
   - `postgres_container` (testcontainers): spins fresh DB per session
   - `db_session`: per-test transaction, rolled back at teardown
   - `client`: httpx AsyncClient bound to FastAPI app via ASGITransport
   - `redis_container`
   - `org_factory`, `user_factory` (polyfactory) — once Phase 2 lands
8. **First placeholder test** (`tests/unit/test_smoke.py`): asserts `1 + 1 == 2`. Proves the runner works.
9. **First component test** (`apps/web/__tests__/smoke.test.tsx`): renders a div, asserts it's there.
10. **GitHub Actions CI.** Jobs: `python-lint`, `python-test`, `web-lint`, `web-test`, `web-build`. Cache uv + pnpm. Run on push to main + every PR.
11. **`.env.example`** — every key with placeholder: `DATABASE_URL`, `REDIS_URL`, `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `SLACK_SIGNING_SECRET`, `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `WEBHOOK_PUBLIC_URL`.
12. **`docs/DEV_SETUP.md`** — step-by-step:
    1. clone, copy `.env.example` → `.env`, fill secrets
    2. `make up`
    3. `make migrate` (waits for postgres healthy)
    4. visit `http://localhost:8000/api/v1/health`
    5. visit `http://localhost:3000`
    6. `make ngrok` → paste URL into Slack app config
13. **Commit.** `feat(phase-1): infra — docker-compose, plugins, pre-commit, CI`.

## Test plan

Phase 1 has no business logic, so the tests are *meta-tests* — they
prove the harness itself works:

- `make test-unit`: runs `pytest tests/unit -q`. Smoke test passes.
- `make test-integration`: runs `pytest tests/integration -q`. Empty
  but exits 0.
- `make e2e`: Playwright opens `http://localhost:3000`, asserts the
  page loads. Skip if no web yet (phase 9) — placeholder.
- `pre-commit run --all-files`: clean.
- `make lint`: clean.
- Commit a deliberately bad file; pre-commit blocks it; revert.

## Definition of done

- [ ] `make up` brings 6 services healthy in <90s
- [ ] `make test` runs and passes (placeholder)
- [ ] `make lint` clean
- [ ] Pre-commit hook installed; blocks bad commits
- [ ] GitHub Actions CI green on push
- [ ] `.env.example` has every key needed for full stack
- [ ] `DEV_SETUP.md` walks a new user from clone to running in <10 minutes
- [ ] ngrok command + Slack URL paste documented
- [ ] One commit on `feat/phase-1-infra` branch, merged to `main`

## Common pitfalls

- **pgvector not installed in postgres image.** Use `pgvector/pgvector:pg17` image, not plain `postgres:17`. Saves an init script.
- **Celery worker can't import the app.** PYTHONPATH issue. Make sure `apps/api/src` is in `PYTHONPATH` or `pip install -e .` in the Dockerfile.
- **httpx + FastAPI testing.** Need `transport = ASGITransport(app=app)` then `AsyncClient(transport=transport)`. Direct `AsyncClient(app=app)` is deprecated.
- **testcontainers slow on first run.** First pull is 30s+. Cache the image in CI: `docker pull pgvector/pgvector:pg17` in a `setup` step.
- **Pre-commit running pytest on every commit = slow.** Use `--quick` profile that only runs tests under `tests/unit/`. Full integration runs in CI.
- **Husky + pnpm path issues on macOS.** Use `pnpm dlx husky install` after install; document in DEV_SETUP.
- **CI fails because secrets not set.** Anthropic/Voyage/Auth0 keys not needed for lint+typecheck+unit tests. Only integration tests against external APIs need them, and those are skipped if env vars missing (`@pytest.mark.skipif`).

## Recap — what you'll be able to explain after this phase

- "How do you run this locally?" → `make up`. Six services come
  up in docker-compose: postgres+pgvector, redis, api (hot reload),
  celery worker, celery beat, web (Next.js dev server).
- "Why testcontainers instead of a shared dev DB?" → Test
  isolation. Every pytest session gets a fresh disposable Postgres.
  No shared state, no order-dependent flakes. CI and local run the
  same code.
- "How do tests stay fast?" → Unit tests don't touch the DB; they
  hit pure functions. Integration tests share one container per
  session and use per-test transactions that roll back at teardown.
- "How does CI mirror local?" → Same Make targets (`make lint`,
  `make test`) in both. GH Actions just shells out to them. Zero
  divergence.
- "How do webhooks reach localhost?" → ngrok exposes port 8000 to
  a public URL. We paste that URL into the Slack app config. In
  production, ngrok is replaced by the actual public ALB hostname.
- "Why pre-commit hooks?" → Catch lint/type errors before they
  reach a PR. Fast feedback loop. The same checks run in CI so
  the hook is just an early warning.

## Talking points (for the grill)

1. **"Local dev parity with CI."** Same Make targets, same lint
   rules, same test runner. No "works on my machine."
2. **"Testcontainers, not shared DB."** Isolation > shared state.
3. **"Pre-commit + CI = defence in depth."** Catch lint locally;
   prove on CI; impossible to merge broken code.
4. **"Hot reload for both API and web in compose."** Tight loop.
5. **"ngrok is dev-only."** Production uses the real public DNS.
   The Slack signature verification doesn't care which URL — only
   the secret matters.
6. **"Bone-stock containers."** `pgvector/pgvector:pg17` and
   `redis:7-alpine`. No custom images to maintain.
