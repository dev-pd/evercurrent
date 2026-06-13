# Contributing to EverCurrent

## Branch + commit conventions

- Branches: `feat/phase-N.M-short-description`.
- Commits follow Conventional Commits: `feat:`, `fix:`, `refactor:`,
  `chore:`, `docs:`. Scope is the phase: `feat(phase-2.3): ...`.
- One commit per subphase. Atomic. No drive-by changes.
- Attribution is empty by design — no `Co-Authored-By` (see
  `.claude/settings.json`).

## Local setup (docker-only)

```bash
cp .env.example .env  # ANTHROPIC_API_KEY + VOYAGE_API_KEY optional
make up               # build + start all six services
make migrate          # apply Alembic migrations
make seed             # load seed data (project, users, channels,
                      # messages, docs)
make ps               # see service status
```

Everything else runs in docker:

- `make lint` → ruff + ty + eslint + prettier + tsc inside docker.
- `make fmt` → ruff format + prettier write inside docker.
- `make test` → pytest unit (health + ready) inside docker.
- `make eval` → scoring + determinism eval suite inside docker.
- `make psql` → psql shell against the running Postgres.
- `make shell-bash` → bash inside the api container.

## Test policy

Per `AGENTS.md §11`: the only test code allowed is

- `apps/api/tests/evals/*` (eval harness with metric reporting).
- `apps/api/tests/unit/test_health.py` and `tests/unit/test_ready.py`.

No other unit tests, no integration tests, no Vitest, no Playwright.
Phase tasks in the build doc that ask for other tests are superseded
and should be skipped (and called out in the subphase commit message).

## Adding a new feature

1. Restate the goal and the files you'll create / modify in your PR
   description.
2. If a `.claude/skills/` skill matches (add-fastapi-route,
   add-react-component, add-celery-task, add-llm-prompt, add-db-migration),
   follow that skill.
3. New external dependencies require a paragraph of justification in
   the PR — the locked stack is deliberate.

## Database changes

- All DDL goes through Alembic. Never edit a merged migration.
- Run `make migration name="add foo table"` to autogenerate.
- Hand-review the diff. Autogenerate does NOT pick up:
  - new pgvector indexes
  - `CREATE EXTENSION`
  - check constraints with custom names
  - HNSW operator class — must be added manually.

## LLM prompts

- Prompts live in `<module>/prompts/*.txt`. Never inline in Python.
- Outputs parsed via Pydantic `model_config = ConfigDict(strict=True)`
  with `BeforeValidator`s for enum + datetime coercion.
- All LLM calls go through `evercurrent.llm.client.LLMProvider`.
  No raw `anthropic.AsyncAnthropic()` elsewhere.
- Model tier picked via `evercurrent.llm.tiering.model_for(tier)`
  — never hardcode model names.

## Quality gates in CI

Defined in `.github/workflows/ci.yml`. PRs must pass:

- `lint-api` — ruff format check + ruff check + ty check.
- `lint-web` — eslint + prettier check + tsc.
- `test-api` — pytest tests/unit only (per policy).
- `build-api` / `build-web` — docker image build.
