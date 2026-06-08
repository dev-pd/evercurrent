# Phase 0 — Reset

## Goal

Inventory the existing codebase. Delete what doesn't fit the new
architecture. Update the top-level docs so future Claude sessions
(and you) start from a clean baseline. Zero new features.

## Why this phase, this order

The current code was built three weeks ago around a different
mental model: single-tenant, days-of-week digest, mock synthetic
data, no Cards, no MCP, no multi-org. The new design pivots all
of those. Keeping dead code around as we layer the new model on
top will rot — half-working endpoints, stale tests, conflicting
schemas. One day of deletion now saves a week of confusion later.

This is also a forcing function: writing the inventory makes
every architectural change explicit, which is exactly the kind
of thing they'll grill you on.

## Pre-requisites

- `docs/MIGRATION.md` written (file-by-file keep/rewrite/delete).
- `docs/DECISIONS.md` started (so the "why we deleted X" answer
  is already on paper).

## Files touched

### Modified
- `AGENTS.md` — testing strategy flipped to TDD hybrid (already done)
- `CLAUDE.md` — point at new phase docs as authoritative build plan
- `README.md` — rewrite to reflect new pivot (one paragraph)
- `EVERCURRENT_BUILD_DOC.md` — mark as historical, point at `docs/phases/`

### Deleted
- All files listed as DELETE in `docs/MIGRATION.md` — exact list there
- `apps/api/seed_data/` synthetic generators that don't match new schema
- Routes / services / models that assumed single-tenancy
- FE pages / components that don't appear in the new dashboard

### New
- `docs/phases/` directory with all phase docs (this work in progress)
- `docs/DECISIONS.md` skeleton
- `docs/MIGRATION.md` (the inventory itself)

## Tasks

1. Read `docs/MIGRATION.md`. For every "DELETE" row, run `git rm`.
2. For every "REWRITE" row, leave the file in place but stub the body
   with `TODO(phase-N)` — we'll rewrite when its phase fires.
3. Drop old Alembic migrations that touched deleted tables. Squash
   into a single fresh baseline migration (`alembic revision -m "phase-0 reset baseline"`).
4. Update `README.md` to one-paragraph "what is this" + link to
   `docs/PRD.md`, `docs/SYSTEM_DESIGN.md`, `docs/phases/README.md`.
5. Update `EVERCURRENT_BUILD_DOC.md` header: "Historical. New build
   plan: `docs/phases/`."
6. Update `CLAUDE.md`: phase docs are authoritative.
7. Run `make lint`. Repo should be clean.
8. `git commit -m "chore(phase-0): reset codebase for v2 architecture"`.

## Test plan

Phase 0 is deletion, not new behaviour. Tests are about *what doesn't
exist anymore*:

- `make lint` passes (no broken imports from deleted modules).
- `pytest --collect-only` shows zero tests (we deleted them; phase 1
  brings back the test scaffolding).
- `pnpm typecheck` passes on FE (or fails only in known to-be-rewritten
  files marked with `// TODO(phase-N)`).

## Definition of done

- [ ] Every file in `MIGRATION.md` DELETE column is gone
- [ ] Every file in REWRITE column has a `TODO(phase-N)` stub
- [ ] Alembic squashed to one baseline migration
- [ ] `README.md`, `CLAUDE.md`, `EVERCURRENT_BUILD_DOC.md` updated
- [ ] `make lint` clean
- [ ] Repo at HEAD compiles + lints with new structure
- [ ] One commit on `feat/phase-0-reset` branch, merged to `main`

## Common pitfalls

- **"Just keep this, we might need it."** No. Delete. Anything we
  need we'll rewrite cleanly in its phase. Half-living code rots.
- **Forgetting to squash migrations.** If you leave the old
  migrations and write new ones for the new schema, Alembic will
  fail because old migrations reference dropped tables.
- **Deleting files referenced by skills/rules.** Check
  `.claude/skills/` and `.claude/rules/` for hardcoded paths first.
- **Leaving dead frontend routes.** The Next.js app still tries to
  build them. Make sure `app/` has no orphaned page.tsx.

## Recap — what you'll be able to explain after this phase

- "Why are you rewriting instead of incrementing?"
  → Pivot from single-tenant digest to multi-tenant agentic
    platform. Data model changed at the root (org_id everywhere),
    UI changed at the root (cards-first not days-of-week), agent
    model changed (Router + Digest instead of one monolith).
    Retrofit cost > rewrite cost.
- "What did you keep?" → The infrastructure primitives that work:
  SQLAlchemy session factory, structlog setup, LLM client wrapper,
  Voyage embedder adapter, SSE/Redis pub-sub.
- "How did you decide what to delete?" → MIGRATION.md is the
  inventory. Every file got a verdict + reason.
- "What does a clean baseline migration buy you?" → Alembic upgrades
  from empty to current schema in one step. Reviewer can run `make
  up` and have a working DB; no need to understand the history.

## Talking points (for the grill)

1. **"I rewrote, not retrofitted."** Show MIGRATION.md.
2. **"I made the architecture change explicit."** Every change is
   in DECISIONS.md with a *why*.
3. **"I squashed migrations to clean baseline."** Easier onboarding,
   easier to reason about current schema.
4. **"I kept what worked: infra primitives."** Not a clean-room
   rewrite — pragmatic, not ideological.
