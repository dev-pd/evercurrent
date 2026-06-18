# EverCurrent — Scaling, Gaps & Production Hardening

An honest engineering review of where this system would strain in
production, which design decisions are questionable, and how to fix each.
Written so it can be defended in an interview: every claim points at real
code, and every gap has a concrete remedy.

This is a take-home. The **core** decisions are sound (deterministic
ranking + LLM language, idempotent async, DB-enforced tenancy, guarded AI
surfaces, real evals). Most items below are **production-hardening** that
is fair to defer — as long as they're named, which is the point of this
doc. The two to lead with as "known weaknesses I'd fix first":
**scoring fan-out** and **observability**.

See also: `docs/SYSTEM_DESIGN.md` (the runtime flows),
`docs/ARCHITECTURE.md` (layering rationale).

---

## 1. Questionable design decisions (ranked by impact)

### 1.1 Scoring fan-out is O(members × messages) — the first wall
`jobs/tasks/score_message.py:98` loops **every** membership for **every**
inbound message and writes a `scores` row each. 50 members × 10k msgs/day
= **500k rows/day**, most of them ~0 relevance for members who'll never
read that message.

- **Why it's wrong:** compute is at *write-time* (per message, all
  members), but the data is only consumed at *read-time* (per digest, one
  member). You pay for 49 members who don't care.
- **Fix:** move scoring to **digest-build time** — score only the member
  being digested, over their candidate messages. Or pre-filter candidate
  members by subsystem/role overlap *before* scoring, so a `#power`
  message isn't scored for the mechanical team. Trade: a little read-time
  latency for a massive drop in write volume and storage.

### 1.2 Single-project-per-org is hardcoded
`route_message` resolves the project as "first project for the org by
`created_at`." Real teams run many concurrent projects.

- **Fix:** a **channel → project** mapping table plus `project_members`,
  so a message routes to the right project and members scope to projects.
  This is the documented next step; until then the app is single-project.

### 1.3 The frontend data model is half server, half client
The digest is server-rendered (`dashboard/page.tsx` props) with **no
client `useQuery(["digest"])`**, so `invalidateQueries(["digest"])` is a
dead no-op — updates require `router.refresh()`. Some data is
server-fetched, some is SSE-invalidated against queries that don't exist.

- **Why it's wrong:** two data-freshness models fighting each other;
  bug-prone (we hit exactly this: the Regenerate button looked dead).
- **Fix:** pick one. Either pure server components + `router.refresh()`
  on events (current direction — make it consistent), or hydrate client
  `useQuery`s from server-fetched initial data and invalidate those. Not
  a mix.

### 1.4 SSE doesn't scale past one API replica
Each browser tab holds an open connection + a Redis pubsub subscription
pinned to one api process (`api/routes/events.py`). Add a second replica
and you must fan out every publish to every replica; at thousands of
concurrent users this exhausts connections and file descriptors.

- **Fix:** a shared fan-out layer, sticky sessions + a shared
  subscription per channel, or a managed realtime service (Ably/Pusher).
  For low-frequency updates (a daily digest), **short-polling is simpler
  and cheaper** than holding connections open.

### 1.5 RLS via `SET LOCAL`, `pool_size=10`, no pgbouncer
The pattern is correct but fragile — we hit the bug where a transaction
rollback dropped `SET LOCAL app.current_org_id` and the next insert
violated RLS (`eve_insight.py` re-applies it).

- **Gotcha to plan for:** when you add **pgbouncer** for connection
  scaling, *transaction*-pooling mode can break `SET LOCAL` semantics
  (the setting may not survive the way you expect). Test tenant isolation
  under pgbouncer before relying on it; consider session-pooling for the
  app role.

### 1.6 Webhook does signature + DB insert in the request path
The `raw_events` insert happens before the 200 ack. Under DB slowness the
webhook slows → Slack retries → more load.

- **Fix (if it becomes hot):** push the raw payload to Redis immediately,
  ack, and persist `raw_events` in the worker. Keeps the ack path
  DB-independent.

---

## 2. What's missing (verified gaps)

- **Integration tests don't exist.** `tests/integration/` is empty
  (`__init__.py` only), despite the testing strategy specifying
  route→service→DB tests via testcontainers. The security-critical paths
  (RLS, auth) have **no integration coverage** — only unit tests.
- **Observability is partial.** The infra *is* wired: HTTP metrics via
  `prometheus_fastapi_instrumentator` at `/metrics`, scraped by Prometheus;
  container logs aggregated by Loki/promtail; Grafana dashboards
  provisioned; an `llm_cost_usd_total` business metric on every LLM call.
  What's **missing**: OTel **distributed tracing** (`otel_exporter_otlp_endpoint`
  is a config field with no tracer/exporter wired — so no spans across the
  webhook → worker → DB path), plus **SLOs and alerting**. So you can see
  request rate, latency, error rate, and LLM spend, but you can't trace a
  single slow request end-to-end, and nothing pages you.
- **No dead-letter queue.** Retries are solid (`acks_late=True`,
  `autoretry_for`, `retry_backoff`, `max_retries=5` — all present), but a
  task that exhausts retries vanishes into logs. No DLQ, no failure
  surface, no replay.
- **No LLM cost/budget controls.** A circuit breaker and per-org token
  budget are absent. A bad Anthropic day backs the queue up and spikes
  cost silently.
- **No caching layer.** Read-heavy endpoints (today / signals / digest)
  re-hit Postgres on every load.
- **Pagination is a smell** — client-side filtering with `limit 1000`
  appeared in the decisions list. Won't survive real volume.
- **Secrets:** a single Fernet key in env (`CONNECTOR_SECRET_KEY`), no
  rotation, no KMS.
- **Data retention / deletion:** messages persist indefinitely; on-
  disconnect deletion was deferred ("nuke covers the demo"). Real
  customers need GDPR-style deletion.

---

## 3. Scaling — the order things break

| # | Breaks at | Symptom | Fix |
|---|-----------|---------|-----|
| 1 | tens of members | scoring fan-out O(N×M) write storm | score at read-time / pre-filter members (§1.1) |
| 2 | message volume | **LLM cost** (linear with msgs — the real $ driver) | cache tags, cheaper model for obvious cases, token budgets |
| 3 | embeddings | Voyage 3 RPM throttle | paid tier / self-host + batch embed + cache |
| 4 | concurrent users | SSE connection exhaustion | managed realtime / fan-out / short-poll (§1.4) |
| 5 | DB load | OLTP + pgvector on one node | read replicas, partition `messages`/`scores`, pgbouncer (mind RLS) |
| 6 | many orgs | noisy neighbor: one org's burst starves others | per-org fair queuing, separate queues per tier |

**Workers scale horizontally already** — tasks are idempotent. The real
win is **separate queues**: Haiku tagging (fast) / Sonnet signals (slow) /
scoring (CPU) / digest, each autoscaled on its own queue depth, so a signal
backlog can't starve tagging.

**The dominant scaling cost is LLM spend, not compute** — it grows
linearly with message volume. Tiering, caching, and sampling are the
levers, not bigger servers.

---

## 4. AI-specific challenges

- **Quality drift.** Prompts/models silently regress. The eval harness
  exists (router / scoring / rag / digest / eve) — make it a **scheduled
  regression run with alerting**, and **gate prompt changes on it**,
  rather than running it on demand.
- **Cost.** See §3 — the dominant cost. Cache tag results for
  identical/near-identical messages; route obvious cases to a cheaper
  path; enforce per-org token budgets with a circuit breaker.
- **Eve confidence is self-reported and uncalibrated.** Does "0.8" mean
  80% correct? Unknown. Calibrate self-rated confidence against the eval
  labels (reliability curve) before trusting the threshold.
- **Trust / human-in-loop.** The grounding gates (digest `_filter_cited_ids`,
  Eve `_gate`) are the right instinct. Next step for high-impact insights:
  a `pending_review` state so a human confirms before it's surfaced.
- **Prompt versioning.** Prompts live in files (good) but aren't
  versioned/pinned to eval results. Tag prompt + eval-score together so a
  regression is traceable to a prompt change.

---

## 5. If I had one sprint to harden this

Ordered by value:

1. **Scoring fan-out** → read-time scoring (kills the write storm).
2. **Observability** → metrics + Grafana already exist; add OTel tracing
   spans (webhook → worker → DB) and alerting on queue depth, LLM
   latency/cost, error rate, eval scores.
3. **Separate Celery queues** + autoscaling (decouple slow Sonnet work).
4. **DLQ + alerting** on exhausted retries.
5. **Integration tests** for RLS + auth (the security spine).
6. **LLM token budgets + circuit breaker.**
7. **Scheduled eval regression** with alerting; gate prompt changes.

Everything else (multi-project, caching, pgbouncer, secret rotation) is
real but lower on the risk-adjusted list.
