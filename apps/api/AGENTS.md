# Backend conventions (`apps/api`)

Loaded for backend work via `apps/api/CLAUDE.md`. Repo-wide standards
(architecture, git, testing) live in the root `AGENTS.md`. This file covers the
non-obvious Python/DB/LLM calls — project decisions my defaults would otherwise
get wrong. The rest (type hints, `strict`, async I/O, no `import *`) is assumed.

## Python

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

## SQL & database

- All DDL via Alembic. Never edit a merged migration.
- snake_case names. `timestamptz` not `timestamp`, default `now()`.
- Every table: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` unless a natural key.
- FKs always specify `ON DELETE`. Indexes deliberate, commented with the query
  they serve.
- pgvector: `vector(512)` for `voyage-3-lite`, HNSW index for ANN.

## LLM & prompts

- All LLM calls go through `src/evercurrent/llm/client.py`. No raw
  `anthropic.AsyncAnthropic()` elsewhere.
- Model tiering in `llm/tiering.py`: `tag()` → Haiku
  (`claude-haiku-4-5-20251001`); `generate_digest()`, `extract_decisions()`,
  `chat_with_tools()` → Sonnet (`claude-sonnet-4-6`). These model ids are
  current — do not substitute older names.
- Prompts in `<module>/prompts/<name>.txt`, never inline. Outputs parsed via
  Pydantic in `<module>/schemas.py`.
- Retry transient errors with tenacity backoff. Log every call: model, in/out
  tokens, latency.

## Footguns

- **RLS tenant context dies on transaction rollback** — `SET LOCAL` is
  transaction-scoped, so a rollback drops it. Re-establish before reuse.
- Backfill cursors are integer epochs, not floats.
</content>
