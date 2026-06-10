# Migration — old codebase → v2 architecture

Inventory of the current repo (151 items) with a verdict per file:
**KEEP** (works as-is), **REWRITE** (file stays, body replaced in
its phase), **DELETE** (gone in Phase 0).

This file is the input to Phase 0. After Phase 0 lands, every row
marked DELETE is gone; every REWRITE is stubbed with
`TODO(phase-N)` until its phase fires.

## Verdict legend

| Verdict | Meaning |
|---|---|
| KEEP | Survives the pivot intact |
| REWRITE@N | File stays at same path; body replaced in Phase N |
| DELETE | Removed in Phase 0 |
| MOVE→X | Path changes; content adapts in target phase |

---

## Backend Python — `apps/api/src/evercurrent/`

### Root

| File | Verdict | Reason |
|---|---|---|
| `__init__.py` | KEEP | package marker |
| `main.py` | REWRITE@1 | FastAPI factory needs new middleware (Auth0+RLS) + new routers |
| `config.py` | REWRITE@1 | new env vars (Auth0, ngrok URL, MCP); strict Pydantic Settings |
| `realtime.py` | KEEP | SSE/Redis pub-sub plumbing reusable |

### `domain/`

Pure domain models from old single-tenant design. Most need an
`org_id` field, and the digest/decisions models change shape under
the Cards model.

| File | Verdict | Reason |
|---|---|---|
| `domain/users.py` | REWRITE@2 | becomes OrgMembership + ProjectMember |
| `domain/projects.py` | REWRITE@2 | add `org_id`, keep milestones/phase model |
| `domain/messages.py` | KEEP | shape mostly matches new `messages` table |
| `domain/documents.py` | REWRITE@10 | extend for `kind`, `phases`, source provenance |
| `domain/digests.py` | REWRITE@8 | swap `day` → `day_index`; add `card_ids` |
| `domain/decisions.py` | REWRITE@6 | becomes `Card` (decision is a kind of card) |

### `db/`

| File | Verdict | Reason |
|---|---|---|
| `db/session.py` | KEEP | async engine factory works as-is |
| `db/models.py` | REWRITE@0 | full schema swap to v2 (see SYSTEM_DESIGN.md §2) |
| `db/repositories/users.py` | REWRITE@2 | becomes membership repo |
| `db/repositories/projects.py` | REWRITE@2 | add org scoping |
| `db/repositories/documents.py` | REWRITE@10 | extend |
| `db/repositories/messages.py` | KEEP | core shape reusable, add `org_id` filter via RLS |
| `db/repositories/channels.py` | REWRITE@3 | becomes `connector_channels` repo |
| `db/repositories/decisions.py` | DELETE | replaced by `cards/repository.py` (Phase 6) |
| `db/repositories/digests.py` | REWRITE@8 | new schema |
| `db/repositories/feedback.py` | REWRITE@7 | merges into `scoring/repository.py` |

### `api/`

| File | Verdict | Reason |
|---|---|---|
| `api/deps.py` | REWRITE@2 | new deps: `get_current_membership`, `get_current_org` |
| `api/middleware.py` | REWRITE@2 | Auth0 verify + set RLS context |
| `api/schemas.py` | REWRITE@N | grows per phase |
| `api/routes/__init__.py` | REWRITE@1 | router wiring rebuild |
| `api/routes/users.py` | DELETE | replaced by `/me` endpoint in `auth` (Phase 2) |
| `api/routes/projects.py` | REWRITE@2 | new endpoints per SYSTEM_DESIGN.md §3.2 |
| `api/routes/documents.py` | REWRITE@10 | new endpoints |
| `api/routes/digests.py` | REWRITE@8 | new endpoints |
| `api/routes/decisions.py` | MOVE→`cards.py`@6 | renamed Cards |
| `api/routes/agent.py` | DELETE | chat agent is roadmap, no longer take-home scope |
| `api/routes/feedback.py` | REWRITE@7 | topic_weights update endpoint |
| `api/routes/events.py` | KEEP | SSE endpoint, plumbing intact |
| `api/routes/today.py` | REWRITE@2 | now returns project today state for dashboard |
| `api/routes/jobs.py` | KEEP | Celery job status polling, generic |

### `llm/`

| File | Verdict | Reason |
|---|---|---|
| `llm/client.py` | KEEP | Anthropic wrapper + audit log already done well |
| `llm/tiering.py` | KEEP | Haiku/Sonnet selection helper |
| `llm/__init__.py` | KEEP | |

### `rag/`

| File | Verdict | Reason |
|---|---|---|
| `rag/embedder.py` | KEEP | Voyage adapter; minor extend in Phase 10 |
| `rag/chunker.py` | REWRITE@10 | replaced with paragraph-aware PyMuPDF chunker |
| `rag/indexer.py` | KEEP | pgvector insert helper |
| `rag/retriever.py` | REWRITE@4 | becomes MCP tool `search_documents` |

### `scoring/`

| File | Verdict | Reason |
|---|---|---|
| `scoring/engine.py` | REWRITE@7 | new weights + signals |
| `scoring/weights.py` | REWRITE@7 | new config |
| `scoring/dependencies.py` | DELETE | DI handled at higher level now |

### `enrichment/`

Becomes part of `routing/` (Phase 5). The old enrichment tagger is
the seed of the Router agent.

| File | Verdict | Reason |
|---|---|---|
| `enrichment/tagger.py` | MOVE→`routing/router_agent.py`@5 | Router replaces it |
| `enrichment/schemas.py` | MOVE→`routing/schemas.py`@5 | becomes RouterDecision |

### `decisions/` (old extractor)

Merged into Cards builder.

| File | Verdict | Reason |
|---|---|---|
| `decisions/extractor.py` | DELETE | replaced by `cards/builder.py` |
| `decisions/schemas.py` | DELETE | replaced by `cards/schemas.py` |

### `digest/`

| File | Verdict | Reason |
|---|---|---|
| `digest/generator.py` | REWRITE@8 | becomes `digest/agent.py` (tool-using) |
| `digest/__init__.py` | KEEP | |

### `agent/` (old chat agent — chat is now roadmap)

| File | Verdict | Reason |
|---|---|---|
| `agent/runner.py` | DELETE | chat moved to roadmap |
| `agent/tools.py` | MOVE→`mcp/tools/`@4 | tools live under MCP server now |
| `agent/streaming.py` | DELETE | not needed without chat |

### `jobs/`

| File | Verdict | Reason |
|---|---|---|
| `jobs/celery_app.py` | KEEP | Celery init + Beat config base |
| `jobs/celery_tasks.py` | REWRITE@N | rebuilt task by task per phase |
| `jobs/worker.py` | KEEP | worker entry + signal handlers |
| `jobs/tasks/__init__.py` | KEEP | |
| `jobs/tasks/ingest_doc.py` | REWRITE@10 | new ingest pipeline |
| `jobs/tasks/enrich_messages.py` | DELETE | becomes `route_message` in routing/ |
| `jobs/tasks/extract_decisions.py` | DELETE | becomes `build_card` in cards/ |
| `jobs/tasks/generate_digests.py` | REWRITE@8 | per-user, day-indexed |
| `jobs/tasks/refresh_today.py` | DELETE | "today" now derived from queries |
| `jobs/tasks/advance_day.py` | DELETE | day model gone; real-time clock |
| `jobs/tasks/regenerate_user_digest.py` | KEEP | manual regen, generalized |

### `ingestion/`

| File | Verdict | Reason |
|---|---|---|
| `ingestion/seeder.py` | DELETE | new seed scripts per Phase 3 (Slack) + Phase 10 (PDFs) |

---

## Database migrations — `apps/api/alembic/versions/`

All four migrations are squashed into a single Phase 0 baseline
migration: `phase_0_v2_baseline.py`. The originals stop applying.

| File | Verdict |
|---|---|
| `20260516_0410_0001_initial_schema.py` | DELETE (squashed) |
| `20260517_0700_0002_digests_per_phase.py` | DELETE (squashed) |
| `20260517_0730_0003_doc_phases.py` | DELETE (squashed) |
| `20260517_0830_0004_project_start_date.py` | DELETE (squashed) |
| (new) `phase_0_v2_baseline.py` | NEW@0 | full v2 schema |
| (new) `phase_2_auth_tables.py` | NEW@2 | orgs + memberships + RLS |
| (new) `phase_3_connectors.py` | NEW@3 | connectors + channels |
| (new) `phase_5_message_tags.py` | NEW@5 | tags table |
| (new) `phase_6_cards.py` | NEW@6 | cards + card_sources + edges |
| (new) `phase_7_scores.py` | NEW@7 | scores table |
| (new) `phase_10_documents.py` | NEW@10 | documents + chunks (pgvector) |
| (new) `phase_11_notifications.py` | NEW@11 | notifications + subscriptions |

(The "v2 baseline" approach: start with the most basic empty schema;
each subsequent phase adds its tables via its own migration. Cleaner
audit trail than one mega-migration.)

---

## Seed data — `apps/api/seed_data/`

Old synthetic message generators are days-of-week shaped. New
demo flow is real Slack + real PDFs.

| File | Verdict | Reason |
|---|---|---|
| `users.json` | DELETE | users now seeded via Auth0 |
| `project.json` | REWRITE@1 | minimal one-project seed for dev |
| `channels.json` | DELETE | populated from real Slack install |
| `messages_day_*.json` (×5) | DELETE | replaced by `slack_seed.py` Phase 3 |
| `docs/prd.md` | MOVE→`sample_pdfs/`@10 | convert to PDF for Drive flow |
| `docs/bom.md` | MOVE→`sample_pdfs/`@10 | same |
| `docs/eco_log.md` | MOVE→`sample_pdfs/`@10 | same |
| `docs/test_report_drop.md` | MOVE→`sample_pdfs/`@10 | same |
| `docs/test_report_thermal.md` | MOVE→`sample_pdfs/`@10 | same |
| (new) `seed_data/sample_pdfs/*.pdf` | NEW@10 | 5 hardware PDFs |
| (new) `seed_data/slack_seed.py` | NEW@3 | script that posts demo messages |

---

## Tests — `apps/api/tests/`

| File | Verdict | Reason |
|---|---|---|
| `unit/test_health.py` | KEEP | survives the pivot |
| `unit/test_ready.py` | KEEP | survives the pivot |
| `evals/conftest.py` | KEEP | fixture infra reusable |
| `evals/test_scoring_eval.py` | REWRITE@7 | new scoring engine |
| `evals/data/scoring_scenarios.json` | REWRITE@7 | new scenarios |
| (new) `conftest.py` (root) | NEW@1 | testcontainers + AsyncClient fixtures |
| (new) `unit/test_smoke.py` | NEW@1 | placeholder; proves runner works |
| (new) `unit/test_scoring.py` | NEW@7 | TDD-heavy module |
| (new) `unit/test_chunking.py` | NEW@10 | TDD module |
| (new) `unit/test_rls.py` | NEW@2 | RLS isolation tests |
| (new) `unit/test_slack_signature.py` | NEW@3 | HMAC verify tests |
| (new) `integration/test_router_pipeline.py` | NEW@5 | end-to-end route_message |
| (new) `integration/test_digest_pipeline.py` | NEW@8 | end-to-end digest gen |
| (new) `evals/eval_router.py` | NEW@12 | router accuracy eval |
| (new) `evals/eval_rag.py` | NEW@12 | retrieval precision@5 |
| (new) `evals/eval_digest.py` | NEW@12 | LLM-as-judge |

---

## Frontend — `apps/web/`

| File | Verdict | Reason |
|---|---|---|
| `app/layout.tsx` | REWRITE@9 | Auth0 provider, new theme |
| `app/page.tsx` | REWRITE@9 | redirect logic |
| `app/dashboard/page.tsx` | REWRITE@9 | cards-first layout per PRD §7.2 |
| `app/decisions/page.tsx` | MOVE→`app/decisions/`@9 | becomes Cards list |
| `app/docs/page.tsx` | KEEP | structure ok; data shape changes |
| `components/layout/app-shell.tsx` | REWRITE@9 | new sidebar |
| `components/layout/impersonation-dropdown.tsx` | DELETE | impersonation gone, real Auth0 now |
| `components/ui/button.tsx` | KEEP | shadcn primitive |
| `components/ui/card.tsx` | KEEP | shadcn primitive |
| `components/ui/select.tsx` | KEEP | shadcn primitive |
| `components/ui/spinner.tsx` | KEEP | shadcn primitive |
| `components/digest/digest-card.tsx` | REWRITE@9 | new shape (buckets + citations + feedback) |
| `components/simulation/day-switcher.tsx` | DELETE | day model gone |
| `components/simulation/phase-switcher.tsx` | DELETE | phase progresses naturally |
| `components/simulation/today-banner.tsx` | REWRITE@9 | becomes DigestHeader |
| `lib/api.ts` | REWRITE@9 | Auth0 bearer token wrapper |
| `lib/types.ts` | REWRITE@9 | new Zod schemas (cards, today, digest items) |
| `lib/utils.ts` | KEEP | tailwind classname helper |
| `hooks/use-events.ts` | KEEP | SSE wrapper reusable |
| `stores/impersonation.ts` | DELETE | impersonation gone |
| `providers.tsx` | REWRITE@9 | add Auth0 + TanStack devtools |
| (new) `components/dashboard/*` | NEW@9 | DigestHeader, DigestSection, DigestItemCard, AnomalyBanner, LiveUpdatesBadge |
| (new) `components/cards/*` | NEW@9 | KnowledgeCard, CardSourceList, CardEdgesList |
| (new) `app/connectors/page.tsx` | NEW@3,@10 | install Slack + Drive |
| (new) `app/subscriptions/page.tsx` | NEW@11 | notification prefs |
| (new) `app/settings/page.tsx` | NEW@2 | tz, quiet hours, profile |
| (new) `hooks/{use-today,use-digest,use-cards,use-feedback}.ts` | NEW@9 | |
| (new) `__tests__/*` | NEW@1 | vitest setup + smoke |
| (new) `e2e/dashboard.spec.ts` | NEW@9 | Playwright happy path |

---

## Root config + build

| File | Verdict | Reason |
|---|---|---|
| `pyproject.toml` | REWRITE@1 | add test deps; remove unused |
| `apps/web/package.json` | REWRITE@1 | add test deps + Auth0 SDK |
| `Makefile` | REWRITE@1 | new targets (test-unit, e2e, ngrok) |
| `docker-compose.yml` | REWRITE@1 | add worker + beat services, pgvector image |
| `.env.example` | REWRITE@1 | new env vars |
| `.pre-commit-config.yaml` | REWRITE@1 | extend with vitest hook |
| `README.md` | REWRITE@0 | new pivot description |
| `CLAUDE.md` | REWRITE@0 | point at phases/ as authoritative |
| `AGENTS.md` | KEEP | already updated for TDD |
| `docs/archive/EVERCURRENT_BUILD_DOC.md` | REWRITE@0 | mark historical, link to phases/ |
| (new) `.github/workflows/ci.yml` | NEW@1 | |
| (new) `apps/api/Dockerfile.dev` | NEW@1 | hot reload |
| (new) `apps/web/Dockerfile.dev` | NEW@1 | hot reload |

---

## Docs — `docs/`

| File | Verdict | Reason |
|---|---|---|
| `PRD.md` | KEEP | rewritten in this conversation |
| `SYSTEM_DESIGN.md` | KEEP | written in this conversation |
| `AGENT_VS_WORKFLOW.md` | KEEP | written in this conversation |
| `ARCHITECTURE.md` | REWRITE@0 | refresh for v2 |
| `BACKEND_DEEP_DIVE.md` | DELETE | replaced by SYSTEM_DESIGN.md + phases/ |
| `PRODUCTION_ROADMAP.md` | REWRITE@0 | scope shift (AWS roadmap only) |
| `CONTRIBUTING.md` | REWRITE@0 | new dev setup flow |
| `DEMO_SCRIPT.md` | REWRITE@12 | live demo flow |
| `EVAL_BASELINE.md` | REWRITE@12 | baselines from new evals |
| `LEARNING_NOTES.md` | KEEP | engineer log, grows |
| (new) `MIGRATION.md` (this file) | NEW@0 | |
| (new) `DECISIONS.md` | NEW@0 | ADRs |
| (new) `CODE_TOUR.md` | NEW@12 | interview walkthrough order |
| (new) `DEV_SETUP.md` | NEW@1 | first-run guide |
| (new) `TESTING_STRATEGY.md` | NEW@1 | TDD + evals reference |
| (new) `phases/*` | NEW@0 | this directory |

---

## `.claude/`

Skills + rules survive the pivot — they describe HOW to write
code, not WHAT to build.

| Skill | Verdict | Reason |
|---|---|---|
| `add-fastapi-route/` | KEEP | route scaffold |
| `add-db-migration/` | KEEP | alembic scaffold |
| `add-llm-prompt/` | KEEP | prompt + schema scaffold |
| `add-arq-task/` | REWRITE→`add-celery-task/`@0 | name + body (Arq long gone) |
| `add-react-component/` | KEEP | component scaffold |
| `execute-subphase/` | REWRITE@0 | update to point at `docs/phases/` |
| `python.md` (rule) | KEEP | lint guidance |
| `typescript.md` (rule) | KEEP | lint guidance |

---

## Summary counts

| | DELETE | REWRITE | KEEP | NEW |
|---|---|---|---|---|
| Backend Python | 11 | 27 | 13 | many |
| Migrations | 4 | 0 | 0 | 7 |
| Seed data | 7 | 1 | 0 | 2 |
| Tests | 0 | 2 | 4 | 11 |
| Frontend | 5 | 11 | 6 | many |
| Root config | 0 | 11 | 1 | 3 |
| Docs | 1 | 6 | 4 | 6 |
| `.claude/` | 0 | 2 | 6 | 0 |
| **Totals** | **28** | **60** | **34** | **~29 in Phase 0, more later** |

Phase 0 alone deletes 28 files, marks 60 with `TODO(phase-N)`,
keeps 34 untouched. That's roughly a third of the repo deleted
or stubbed in one commit.
