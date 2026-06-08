# Decisions — Architectural Decision Records

Every architectural choice with a "why we picked this" answer. Skim
before the interview; pre-loaded answers for the grill.

Format: ADR-style. Each decision has Context, Decision, Why this
beats alternatives, Trade-offs, When we'd revisit.

---

## ADR-001 — Multi-tenant via row-level security at the database, not the app layer

**Context.** Multi-tenant SaaS. Every read and write must be
scoped to the user's org. Two ways to enforce this: (a) every query
in app code carries `WHERE org_id = ?`, or (b) Postgres row-level
security (RLS) policies on every table, with a session variable
set by middleware.

**Decision.** RLS at the DB. Middleware sets
`app.current_org_id` per request based on the user's Auth0
membership. Every table has a policy
`USING (org_id = current_setting('app.current_org_id')::uuid)`.

**Why this beats (a).** If a developer forgets to add a `WHERE`
clause, every user sees every other tenant's data — a worst-case
data leak. With RLS, the same bug shows zero rows; failure is safe.

**Trade-offs.** Adds a small set-context overhead per connection
(<1ms). Requires care with connection pooling (must reset variable
on return). Some ORMs need shims. We use SQLAlchemy with an
event listener.

**When we'd revisit.** Never for a multi-tenant SaaS.

---

## ADR-002 — Auth0 over Clerk

**Context.** Need user + org auth. Both Auth0 and Clerk offer it.
JD lists Auth0 explicitly.

**Decision.** Auth0.

**Why.** Stack alignment with the team's existing infrastructure.
Both products are roughly comparable on features (OAuth, orgs,
RBAC, social, MFA). Picking Auth0 reduces onboarding friction and
signals attention to the stated stack.

**Trade-offs.** Clerk's Next.js DX is marginally smoother. We pay
for Auth0's heavier integration in exchange for stack fit.

**When we'd revisit.** If team standardised on Clerk after this.

---

## ADR-003 — FastMCP as the agent tool layer, not bespoke function definitions

**Context.** Agents need tools (`search_messages`, `query_cards`,
etc.). Two approaches: (a) inline tool definitions per agent as
Anthropic SDK requires, (b) expose tools through an MCP server and
have agents call them as a protocol-grade client.

**Decision.** FastMCP server with tools under `mcp/tools/`.
All agents call tools via an in-process MCP client.

**Why.** Three reasons.

1. **Protocol-grade.** Tools are reusable by any agent that speaks
   MCP — our agents today, Claude Desktop tomorrow, the customer's
   own LLM next year.
2. **JD alignment.** The role specifies "MCP, VectorDBs, foundation
   models." Building on MCP from day 1 is the explicit signal.
3. **Future-portable.** Moving the MCP server out-of-process at
   scale is a config change, not a rewrite.

**Trade-offs.** A thin protocol overhead vs. direct function calls.
Negligible (<5ms in-process).

**When we'd revisit.** If MCP ecosystem dies, fall back to inline
tool schemas. Unlikely.

---

## ADR-004 — Postgres + pgvector, not a separate vector DB (Pinecone, Weaviate)

**Context.** RAG needs vector search. Could use a managed vector
DB or extend Postgres with pgvector.

**Decision.** Postgres 17 with pgvector 0.8, HNSW index for ANN.

**Why.**

- **Single store.** Embeddings, metadata, joins, transactions all
  in one place. No two-phase commits, no "DB and vector store out
  of sync" failure mode.
- **RLS-friendly.** pgvector rows inherit the same RLS policies as
  any other table. With Pinecone we'd need to encode tenant in
  the namespace and trust it client-side.
- **No extra hop.** Vector search runs inside the same query plan
  as filtering by org/project/phase.
- **Cost.** Free at our scale.

**Trade-offs.** Specialised vector DBs scale to billions of vectors
with better latency. We're at thousands per project. pgvector
handles it.

**When we'd revisit.** > 100M vectors, p99 latency > 50ms, or
heavy distance-function variety.

---

## ADR-005 — Voyage `voyage-3-lite` (512 dims), not OpenAI ada-002 (1536) or BGE

**Context.** Need embeddings for chunk + query vectors. Choices:
OpenAI ada-002 / text-embedding-3-small (1536), Voyage voyage-3
(1024) or voyage-3-lite (512), open-source BGE-M3 (1024).

**Decision.** `voyage-3-lite`, 512 dimensions.

**Why.**

- **Retrieval quality.** Voyage's 2024–26 models outperform OpenAI
  ada on most domain benchmarks. `voyage-3-lite` matches `voyage-3`
  within ~2 points of MRR on long-form technical text.
- **Cost.** ~$0.02 per 1M tokens; OpenAI is ~3× more.
- **Latency.** 512 dims means smaller index, faster ANN. HNSW
  build time is roughly linear in dimensions.
- **Storage.** 4× smaller than 1536-dim vectors at the same row
  count.
- **No GPU needed.** Skipping BGE removes the self-host burden.

**Trade-offs.** Voyage is a single-vendor dependency. If they
disappear, we re-embed everything with another provider. The
`EmbeddingProvider` interface in `rag/embedder.py` makes the swap
a one-file change.

**When we'd revisit.** When Voyage prices change materially, or
if our retrieval evals show systematic recall failures.

---

## ADR-006 — Push webhooks for ingest, not polling

**Context.** Slack and Drive both support push (webhooks /
file watch channels) and pull (polling APIs). Push needs a
public URL, which locally means ngrok.

**Decision.** Push for both. Locally use ngrok; production uses
the real ALB hostname.

**Why.**

- **Latency.** A new Slack message reaches us in ~1s vs 30s+
  polling.
- **Bandwidth.** Polling wastes API budget on "no, nothing
  changed" responses.
- **Correctness.** Polling needs cursor tracking + "missed since"
  windows + dedupe; push gives us each event exactly once (with
  retry on non-2xx).
- **Production posture.** Polling is what you build when you don't
  know webhooks exist.

**Trade-offs.** Ngrok dependency for local dev. Acceptable: it's
a one-line `make ngrok`. The webhook handler has the same code
path in dev and prod.

**When we'd revisit.** If the connector vendor lacks a push API.

---

## ADR-007 — Celery + Beat for background jobs and scheduling, not Temporal (yet)

**Context.** Need: async webhook handlers, fan-out for digests,
retries, cron. Options: Celery, Temporal, Cloud Tasks, custom.

**Decision.** Celery 5.4 with Redis broker + Celery Beat for cron.

**Why.**

- **Standard.** Python ecosystem default. Lowest onboarding
  friction.
- **Right-sized.** We have stateless tasks with retries and a
  cron — Celery's bread and butter.
- **Fast to set up.** docker-compose service in 10 lines.
- **Beat handles sub-minute scheduling.** Per-user 8am-local
  digest cron is a Beat expression.

**Trade-offs.** Celery doesn't have Temporal's durable multi-step
workflow resume. If a worker dies mid-step in a chain, Celery
re-runs from the task; Temporal would resume from the last
checkpoint within the workflow.

**When we'd revisit.** When we have ≥3 multi-step durable
workflows that lose work on partial failure (e.g., 5-step "process
ECO ingest → infer impact → notify all subscribers" chain). Then
migrate orchestration to Temporal while keeping Celery for
stateless fan-out.

---

## ADR-008 — Two agents (Router + Digest), not one mega-agent

**Context.** Could build one Claude Sonnet agent that handles
classify-message + draft-digest + answer-chat. Or split by job.

**Decision.** Two distinct agents: **Router agent** (Haiku, per
message, classify + tag), **Digest agent** (Sonnet, per user
nightly, write briefing). Linker is a roadmap third. Chat is a
roadmap fourth.

**Why.**

- **Cost.** Router fires 10k+/day. Haiku is ~12× cheaper than
  Sonnet. Wrong tool = ~$30k/year savings at 50 orgs.
- **Latency.** Router must finish in <2s for SSE freshness.
  Sonnet's latency would break the live-update demo.
- **Failure isolation.** Linker breaks → digests still ship. Mega
  agent breaks → product dead.
- **Prompt drift.** Each agent has its own system prompt, tool set,
  Pydantic output schema, and eval suite. Mixing = regression hell.
- **Eval clarity.** Router precision/recall is measured separately
  from digest usefulness. Different KPIs, different judges.

**Trade-offs.** More moving parts, two prompt files instead of
one, two eval suites. Worth it.

**When we'd revisit.** If models drop in cost by 10×+ such that
Sonnet-everywhere is cheaper than the operational overhead of
two agents.

---

## ADR-009 — Precomputed daily digest, not regenerated per message

**Context.** Two extreme designs: (a) Sonnet drafts the digest
fresh every time the user opens the dashboard, (b) precompute
the digest nightly + push live deltas via SSE.

**Decision.** (b). Cron generates one digest per user at user-local
08:00. Inserts/changes during the day arrive as SSE events the FE
merges in.

**Why.**

- **Cost.** Sonnet at $0.05/digest × 200 users × 5 dashboard
  opens/day = $50/day. Precompute: $10/day.
- **Idempotency.** A `digests` row uniquely keyed on
  `(member, day_index)` makes replay safe.
- **Audit trail.** "What was Sarah told on 2026-06-07 morning?"
  is a SQL query.
- **Quality.** Drafting at 8am gives the model time to take its
  time (longer max_tokens). On-demand has a latency budget the
  user feels.

**Trade-offs.** Slightly stale: if a critical thing breaks at
2pm, the morning digest doesn't reflect it. We patch with live
SSE deltas + an "anomaly banner" surface at the bottom.

**When we'd revisit.** If users complain digests are stale.
Likely add a "regenerate" button (already in API spec) before
moving to on-demand.

---

## ADR-010 — Knowledge Cards as the atomic unit, not Slack threads

**Context.** What's the noun the product is built around? Slack
messages, Slack threads, Decisions only, or something new.

**Decision.** **Knowledge Cards.** Each Card is a decision, risk,
or open question. Cards link to N sources (messages, doc chunks,
PRs) and N other Cards (blocks, depends-on).

**Why.**

- **Cross-source by design.** A decision can cite messages, PDF
  chunks, and a PR. The Card is the place those converge.
- **First-class objects.** Cards have status (open/closed), owners,
  affected subsystems, confidence. Slack threads have none of that.
- **Stable IDs.** Cards live in our DB; Slack threads can be
  edited or deleted upstream.
- **The product's narrative.** "Here are the decisions you should
  know about" is exactly Cards. Not "here are messages."

**Trade-offs.** We have to extract Cards from messages — that's
the Router + (later) Linker job. Worth it.

**When we'd revisit.** Never. Cards are the thesis.

---

## ADR-011 — Server components in Next.js by default, not full SPA

**Context.** Next.js 16 App Router supports server components +
streaming. Default could be SPA-style with `"use client"`
everywhere, or server-by-default with interactivity opt-in.

**Decision.** Server components default. `"use client"` only for
components that subscribe to SSE, hold local UI state, or run
event handlers.

**Why.**

- **Less JavaScript.** First contentful paint faster.
- **Simpler auth.** Server components can read the Auth0 cookie
  directly; no extra fetch round-trip.
- **Streaming.** Suspense boundaries let the digest header stream
  while the items load.
- **Type safety.** Server-side fetches use the same Python-typed
  API client code path.

**Trade-offs.** Mental model shift for engineers used to SPAs.
React DevTools shows server components as "boundary;" debugging
takes practice.

**When we'd revisit.** Never — server components are the future.

---

## ADR-012 — TanStack Query for server state, Zustand for client state, no Redux

**Context.** State management. Could use Redux Toolkit, Jotai,
context, TanStack Query, Zustand, anything.

**Decision.** **TanStack Query** for everything that lives on the
server (digests, cards, today, subscriptions). **Zustand** for
ephemeral client UI state (collapsed sections, filter toggles).
No Redux.

**Why TanStack.**

- Server state has its own concerns: cache, invalidation, refetch,
  optimistic updates, deduplication. Redux solves none of these
  out of the box.
- SSE delta → query invalidation → automatic refetch is one line.
- Devtools show queries + cache state at a glance.

**Why Zustand for client state.**

- API is React-flavoured but minimal.
- No provider boilerplate.
- Selectors are functions, not strings.

**Why not Redux.**

- Bulk of our state is server state. TanStack covers it. Adding
  Redux for the 10% of client state is overkill.

**When we'd revisit.** When client state grows to >20 stores or
needs time-travel debugging.

---

## ADR-013 — TDD on deterministic code, eval harness on LLM code (not unit tests)

**Context.** Need a test strategy that gives us confidence without
becoming a maintenance tax. Pure-Python code wants unit tests.
LLM output is non-deterministic — unit tests on it churn.

**Decision.** Hybrid. **TDD (red-green-refactor)** on every
deterministic module: auth, RLS, scoring, cards builder, chunking,
repositories, signature verification, quiet hours math. **Offline
eval harness** for LLM behaviour: router accuracy, RAG
precision@5/MRR, digest quality via LLM-as-judge.

**Why.**

- **Deterministic code is testable.** Same input, same output.
  Tests catch regressions for free.
- **LLM code isn't.** A `assert response == "..."` test fails the
  day the model is upgraded. Useless signal.
- **Eval harness measures what matters.** "Is the agent's output
  good?" — which a string-match test cannot answer.
- **Separation of concerns.** Coverage gate on deterministic code
  (80%); eval baselines tracked in `EVAL_BASELINE.md`.

**Trade-offs.** Two test runners. Two CI gates (one strict — unit
tests; one informational — evals).

**When we'd revisit.** Never. This is the correct shape.

---

## ADR-014 — One commit per phase, conventional commits, no monster PRs

**Context.** Take-home has 12 phases. Could do one commit per
day, one giant PR at the end, or one commit per phase.

**Decision.** One commit per phase. Format:
`feat(phase-N): <description>`. One branch per phase. Merged to
main after the phase's definition-of-done checklist is green.

**Why.**

- **Reviewability.** A reviewer can read the commit log as a
  story.
- **Bisect-friendly.** "What broke between phase 5 and 6?" is one
  command.
- **Discipline.** Forces the phase doc's "definition of done" to
  actually be done before moving on.

**Trade-offs.** Slightly slower iteration than commit-per-task.

**When we'd revisit.** Never in a take-home; in production, each
ticket gets its own commit.

---

## ADR-015 — `pyproject.toml` is the single source of truth (no setup.py, no requirements.txt)

**Context.** Python packaging has three eras of build tooling.
Pick one.

**Decision.** `pyproject.toml` + `uv` for environment + lockfile.

**Why.**

- **One file.** Project metadata, deps, tool configs (ruff, ty,
  pytest), and entry points all live here.
- **Standard.** PEP 621.
- **`uv` is the fastest resolver and installer.** Locks
  reproducibly.

**Trade-offs.** None worth listing.

---

## ADR-016 — Mock-Drive demo mode (read PDFs from disk) alongside real Drive OAuth

**Context.** Demo flow needs to show PDF ingest. Real Drive OAuth
requires Google Cloud project setup + consent screen.

**Decision.** Both modes shipped. Real Drive OAuth is the
production path. A `mock_drive_ingest.py` script reads sample
PDFs from `seed_data/sample_pdfs/` and triggers the same
`ingest_document` Celery task — so the demo can run without any
Google account.

**Why.**

- Live demo on the user's machine works without external setup.
- The "real" path is also fully implemented; we can flip between
  them with a flag.
- Reviewer cannot ding us for "you mocked the integration" —
  both paths exist.

**Trade-offs.** Two entry points to maintain. Tiny — both call
the same task with the same payload shape.

---

## ADR-017 — Demo via live local docker-compose, no cloud deploy

**Context.** Take-home demo: deploy to AWS or run locally?

**Decision.** Local docker-compose. AWS deploy is a roadmap line
item.

**Why.**

- Take-home scope is days, not weeks. AWS adds 2 days for IAM
  alone.
- Reviewer doesn't need to install anything — we run the demo.
- Production infra (VPC, RDS, ECS, ALB, KMS, Secrets Manager)
  is documented in `PRODUCTION_ROADMAP.md` so the architecture
  is on record.

**Trade-offs.** Reviewer can't poke around a live URL. We compensate
with a live walkthrough.

**When we'd revisit.** Day 1 of full-time. Not before.

---

## ADR-018 — Tests run testcontainers Postgres + Redis (not SQLite, not shared dev DB)

**Context.** Where do integration tests run? Options: in-memory
SQLite (wrong dialect), shared dev Postgres (order-dependent
flakes), testcontainers (fresh ephemeral container per session).

**Decision.** testcontainers. One container per pytest session,
per-test transaction rolled back at teardown.

**Why.**

- **Same dialect as production.** pgvector, RLS, JSONB all work
  exactly like prod.
- **Isolation.** No "did the previous test leave a row behind?"
- **CI + local parity.** Same code path; CI just pulls the image.

**Trade-offs.** First-run pull is 30s. Cached on subsequent runs.
CI caches the image in a setup step.

**When we'd revisit.** Never for integration tests.

---

## Decisions to revisit before the interview

Stub list of things we punted on and want to be honest about:

- **Linker agent** — designed, not built in take-home. Phase doc
  exists, would land week 2.
- **Timeline / Gantt** — designed, not built. Same.
- **AWS deploy** — designed, not built. PRODUCTION_ROADMAP.md is
  the answer.
- **GitHub + Jira connectors** — designed, not built. Two more
  connectors plug into the same Connector Protocol.
- **OpenTelemetry tracing** — local logs only; OTel collector +
  Tempo is roadmap.

Honest answer when grilled: "I optimised for depth on the agentic
pipeline + multi-tenancy. These were the items I deliberately
deferred so I could ship the hero feature with quality."
