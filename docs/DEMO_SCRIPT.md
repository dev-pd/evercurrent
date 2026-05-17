# EverCurrent — Demo Script

Five-minute walkthrough. Backend-heavy: the dashboard is intentionally
thin; the depth lives in the queue + the pipeline.

## Minute 1 — the framing

Hardware teams have knowledge scattered across Slack, MCAD, Jira,
Confluence. A mech engineer doesn't read the supply chain channel,
but when a supplier strike hits the aluminum extrusion her bracket
needs, she needs to know **today**. EverCurrent's positioning is
cross-functional dependency tracking, decision extraction, and a
continuously updating, role-aware briefing — not generic summarisation.

## Minute 2 — the live pipeline

Open `http://localhost:8080/dashboard` impersonated as Sarah Chen
(mech_eng).

- Top banner shows `Live · Sat, May 17 · phase DVT · N messages today
  · last inbound 12s ago · digest refreshed 18s ago · SSE — server
  pushes updates`.
- Open browser devtools → Network. One persistent `/api/events?...`
  connection, no periodic polls. Inspect the stream — SSE events
  arrive as `digest.updated`, `message.synthesized`, `phase.changed`.
- Behind the scenes: Celery beat fires `synthesize_today_message`
  every 60s (Sonnet writes 2 phase-scoped messages), `refresh_today`
  every 30s (Haiku tags, Sonnet rewrites digests for every user under
  the current phase, decisions get extracted).
- When the worker writes, it `redis.publish("events:{project_id}",
  ...)`. The `/events` SSE relay subscribes + pushes to the browser.
  TanStack Query invalidations re-fetch.

## Minute 3 — personalisation + phase

- Switch impersonation Sarah → Mei (supply_chain). Same underlying
  messages, different digest. Sarah leads with ECO-178, AL-7075-T6
  sourcing, thermal failures. Mei leads with extrusion sourcing +
  AlumWest cost premium.
- Switch user back. Flip phase DVT → PVT in the dropdown. The
  dashboard re-renders within ~50ms — every (user, day, phase) digest
  is precomputed. **No LLM call in the request path** for phase swap.
- For a cell that hasn't been precomputed, the dashboard enqueues a
  `regenerate_user_digest` task transparently and shows "Showing
  cached <X> — <Y> variant building". Task completes in ~10s, SSE
  pushes `digest.updated`, panel refetches.

## Minute 4 — decisions + docs

- Open Decisions. Sonnet extracted ~20 decisions across the seed
  data. Each carries status, affected subsystems, confidence,
  source message ids. The filter narrows to decisions whose affected
  subsystems intersect the impersonated user's owned subsystems.
- Open Documents. Each doc is tagged with the project phases it is
  authoritative for. The RAG retriever filters by the active project
  phase so it doesn't cite a thermal test report when the project is
  in `design`.

## Minute 5 — eval + production story

- Terminal: `make eval`. 6/6 scoring scenarios + 2 determinism checks.
  `docs/EVAL_BASELINE.md` shows targets for LLM-as-judge digest eval +
  RAG retrieval eval (forward work).
- Walk `docs/PRODUCTION_ROADMAP.md` top three sections in 30s each:
  - **Real Slack adapter** behind `IngestionAdapter` interface; OAuth
    + Events API + rate-limited backfill replacing
    `synthesize_today_message`.
  - **ITAR / SOC 2** with regional Anthropic endpoints, audit logs,
    PII redaction step around every LLM call.
  - **Observability** — per-tenant cost dashboard sliced by Haiku /
    Sonnet / Voyage; nightly eval regression alerts.
- Close with: "The dashboard is a read-only viewport on a pipeline
  whose every layer is independently testable + swappable. Slack
  webhook in, decisions + personalised digests out, Celery in the
  middle, Postgres + pgvector underneath."
