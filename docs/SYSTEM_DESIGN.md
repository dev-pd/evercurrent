# EverCurrent — System Design

Companion to `PRD.md`. PRD answers "what are we building." This
answers "how do we build it."

## 0. Build order — yes, you've got it right

The order you proposed is correct, with one nuance:

```
1. Feature spec       (what)       ← PRD.md
2. Data model         (nouns)      ← this doc, §2
3. API contract       (verbs)      ← this doc, §3
4. Backend services   (logic)      ← this doc, §4
5. Frontend           (surface)    ← this doc, §5
```

**Why this order:**

- You can't design a table without knowing what feature it supports.
- You can't design an API without knowing what tables it reads/writes.
- You can't build a UI without knowing what data the API gives back.

**The nuance:** steps 2 + 3 + 5 loop. Sketching a screen sometimes
reveals you need a field in the API → which reveals you need a
column in the table. So you don't finish the data model, then move
on — you draft it, draft the API, draft the screen, then come back
and tighten everything. Two or three quick loops, not one big
waterfall.

**Concrete order for EverCurrent's take-home scope:**

1. Sign-in + organisations (Clerk + RLS) — proves multi-tenancy works
2. Slack install + message ingest — proves data flows in
3. Router agent — proves the agent can tag a message
4. Knowledge Cards table — proves we have the atomic unit
5. Digest agent — the hero feature
6. Dashboard (cards-first UI) — what the demo opens to
7. Slack DM delivery + subscriptions — proves the loop closes

---

## 1. Architecture — the big picture

```
┌───────────────────────────────────────────────────────────────────┐
│                          BROWSER                                  │
│  Next.js app: dashboard, timeline, decisions, settings            │
└───────────────────┬───────────────────────────────────────────────┘
                    │  HTTPS — JSON over fetch + SSE for live updates
                    │  Clerk session cookie for auth
                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                       FastAPI (Python)                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Middleware: Clerk verify → set org_id for RLS              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Routes: /api/projects, /api/cards, /api/digests, /events   │ │
│  └──────────┬──────────────────────────────────────────────────┘ │
│  ┌──────────▼──────────────────────────────────────────────────┐ │
│  │  Services: cards, digest, scoring, routing                  │ │
│  └──────────┬──────────────────────────────────────────────────┘ │
│  ┌──────────▼──────────────────────────────────────────────────┐ │
│  │  Repositories: SQLAlchemy async sessions                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────┬────────────────────────┬──────────────────────┘
                    │                        │
                    ▼                        ▼
       ┌─────────────────────┐    ┌────────────────────┐
       │   Postgres 17       │    │     Redis          │
       │   + pgvector        │    │  Celery broker     │
       │                     │    │  Pub/sub for SSE   │
       │  All persistent     │    │  Per-job state     │
       │  state lives here   │    └────────────────────┘
       └─────────────────────┘             │
                                           │ subscribes to "events:<org>"
                                           ▼
┌───────────────────────────────────────────────────────────────────┐
│                       Celery worker                               │
│  Background jobs: route_message, generate_digest, ingest_doc      │
│  Celery Beat: nightly digest cron, periodic connector poll        │
└────┬───────────────────┬───────────────────┬──────────────────────┘
     │                   │                   │
     ▼                   ▼                   ▼
┌──────────┐      ┌────────────┐      ┌─────────────┐
│ Slack    │      │ Anthropic  │      │ Voyage AI   │
│ webhook  │      │ Haiku/     │      │ embeddings  │
│ + Web    │      │  Sonnet    │      │             │
│ API      │      └────────────┘      └─────────────┘
└──────────┘
```

**One-paragraph version:**

Browser talks to FastAPI over HTTPS. FastAPI checks the user's Clerk
cookie, looks up which org they belong to, sets a Postgres setting
so every query is filtered to that org. Read endpoints return JSON.
Live updates come over SSE (server-sent events) by subscribing to
Redis. Write endpoints + slow work (LLM calls, ingestion) go on a
Celery queue. Celery workers do the heavy lifting and publish events
back to Redis when done, which closes the loop to the browser.

---

## 2. Data model

### 2.1 Naming + conventions

- All IDs: `UUID` primary keys, default `gen_random_uuid()`.
- All timestamps: `timestamptz` (timezone-aware), default `now()`.
- All tenant-scoped tables get an `org_id` foreign key and
  Postgres row-level security so a user can never accidentally
  read another org's rows.
- All foreign keys declare `ON DELETE` behaviour explicitly
  (`CASCADE`, `SET NULL`, or `RESTRICT`).

### 2.2 Tables — what each one is for

```
orgs                  one row per customer company
org_memberships       which user is in which org, with what role
projects              one row per engineering project inside an org
project_members       which user is on which project, with what subsystems
connectors            "Slack is installed", "Drive is installed"
connector_channels    "ingest #mech-design, ignore #random"
raw_events            untouched payload from a webhook (audit trail)
messages              normalised Slack/Drive/PR message
message_tags          router agent's output: topic, urgency, entities
documents             a PDF or Google Doc, after ingest
document_chunks       split-up doc text + vector embedding
cards                 a decision, risk, or open question (atomic unit)
card_sources          which messages/docs this card was built from
edges                 "card A blocks card B" — graph relationships
scores                per-user, per-message relevance score
digests               the daily briefing for one user
notifications         what we sent to whom, when, which channel
subscriptions         what each user opted into being notified about
audit_log             every LLM call, ingest event, notification sent
```

### 2.3 Detailed schema (take-home scope)

```sql
-- ============== Multi-tenancy ==============

CREATE TABLE orgs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_org_id    TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  plan            TEXT NOT NULL DEFAULT 'free',
  region          TEXT NOT NULL DEFAULT 'us-east',
  itar            BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE org_memberships (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  clerk_user_id   TEXT NOT NULL,
  slack_user_id   TEXT,
  display_name    TEXT NOT NULL,
  email           TEXT NOT NULL,
  role            TEXT NOT NULL CHECK (role IN ('admin','member')),
  timezone        TEXT NOT NULL DEFAULT 'UTC',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (org_id, clerk_user_id)
);

-- ============== Project + members ==============

CREATE TABLE projects (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  current_phase   TEXT NOT NULL,
  start_date      DATE NOT NULL,
  milestones      JSONB NOT NULL DEFAULT '[]',
  phase_concerns  JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX projects_org_idx ON projects(org_id);

CREATE TABLE project_members (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  membership_id     UUID NOT NULL REFERENCES org_memberships(id) ON DELETE CASCADE,
  role              TEXT NOT NULL,
  owned_subsystems  TEXT[] NOT NULL DEFAULT '{}',
  owned_parts       TEXT[] NOT NULL DEFAULT '{}',
  topic_weights     JSONB NOT NULL DEFAULT '{}',
  UNIQUE (project_id, membership_id)
);

-- ============== Connectors (Slack, Drive, etc.) ==============

CREATE TABLE connectors (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  kind                TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'active',
  external_team_id    TEXT,
  credentials_secret  TEXT NOT NULL,
  installed_by        UUID REFERENCES org_memberships(id),
  installed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (org_id, kind)
);

CREATE TABLE connector_channels (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  connector_id    UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
  external_id     TEXT NOT NULL,
  name            TEXT NOT NULL,
  ingest          BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (connector_id, external_id)
);

-- ============== Ingest ==============

CREATE TABLE raw_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  source        TEXT NOT NULL,
  external_id   TEXT NOT NULL,
  payload       JSONB NOT NULL,
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, external_id)
);

CREATE TABLE messages (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  project_id          UUID REFERENCES projects(id) ON DELETE SET NULL,
  source              TEXT NOT NULL,
  external_id         TEXT NOT NULL,
  channel             TEXT,
  thread_root_id      UUID REFERENCES messages(id) ON DELETE SET NULL,
  author_membership_id UUID REFERENCES org_memberships(id),
  author_display_name TEXT NOT NULL,
  text                TEXT NOT NULL,
  posted_at           TIMESTAMPTZ NOT NULL,
  ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, external_id)
);
CREATE INDEX messages_org_posted_idx ON messages(org_id, posted_at DESC);
CREATE INDEX messages_project_posted_idx ON messages(project_id, posted_at DESC);

CREATE TABLE message_tags (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  topic           TEXT,
  urgency         TEXT,
  entities        TEXT[] NOT NULL DEFAULT '{}',
  affected_roles  TEXT[] NOT NULL DEFAULT '{}',
  tagged_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  tagged_by_model TEXT NOT NULL,
  UNIQUE (message_id)
);

-- ============== Documents + chunks ==============

CREATE TABLE documents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  project_id  UUID REFERENCES projects(id) ON DELETE SET NULL,
  source      TEXT NOT NULL,
  external_id TEXT NOT NULL,
  kind        TEXT NOT NULL,
  title       TEXT NOT NULL,
  phases      TEXT[] NOT NULL DEFAULT '{}',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, external_id)
);

CREATE TABLE document_chunks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ordinal       INT NOT NULL,
  section       TEXT,
  text          TEXT NOT NULL,
  embedding     vector(512) NOT NULL,
  UNIQUE (document_id, ordinal)
);
CREATE INDEX doc_chunks_hnsw_idx ON document_chunks
  USING hnsw (embedding vector_cosine_ops);

-- ============== Knowledge Cards ==============

CREATE TABLE cards (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind                TEXT NOT NULL,
  summary             TEXT NOT NULL,
  body                TEXT,
  status              TEXT NOT NULL DEFAULT 'open',
  owner_membership_id UUID REFERENCES org_memberships(id),
  affected_subsystems TEXT[] NOT NULL DEFAULT '{}',
  confidence          REAL,
  decided_at          TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX cards_org_project_idx ON cards(org_id, project_id, created_at DESC);

CREATE TABLE card_sources (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id     UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
  source_kind TEXT NOT NULL,
  source_id   UUID NOT NULL
);
CREATE INDEX card_sources_card_idx ON card_sources(card_id);

CREATE TABLE edges (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  from_kind    TEXT NOT NULL,
  from_id      UUID NOT NULL,
  to_kind      TEXT NOT NULL,
  to_id        UUID NOT NULL,
  edge_type    TEXT NOT NULL,
  confidence   REAL,
  inferred_by  TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX edges_from_idx ON edges(from_kind, from_id);
CREATE INDEX edges_to_idx ON edges(to_kind, to_id);

-- ============== Scoring + digest ==============

CREATE TABLE scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_member_id UUID NOT NULL REFERENCES project_members(id) ON DELETE CASCADE,
  message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  score           REAL NOT NULL,
  reasons         JSONB NOT NULL DEFAULT '{}',
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_member_id, message_id)
);
CREATE INDEX scores_member_score_idx
  ON scores(project_member_id, score DESC);

CREATE TABLE digests (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_member_id UUID NOT NULL REFERENCES project_members(id) ON DELETE CASCADE,
  day_index         INT NOT NULL,
  phase             TEXT NOT NULL,
  content_md        TEXT NOT NULL,
  card_ids          UUID[] NOT NULL DEFAULT '{}',
  message_ids       UUID[] NOT NULL DEFAULT '{}',
  generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_member_id, day_index)
);

-- ============== Notifications + subscriptions ==============

CREATE TABLE subscriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  membership_id   UUID NOT NULL REFERENCES org_memberships(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,
  value           TEXT,
  enabled         BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE notifications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  membership_id   UUID NOT NULL REFERENCES org_memberships(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,
  payload         JSONB NOT NULL,
  channel         TEXT NOT NULL,
  sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  opened_at       TIMESTAMPTZ,
  clicked_at      TIMESTAMPTZ
);

-- ============== Audit ==============

CREATE TABLE audit_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,
  actor           TEXT NOT NULL,
  payload         JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_org_created_idx ON audit_log(org_id, created_at DESC);
```

### 2.4 Row-level security

Every tenant-scoped table gets:

```sql
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON messages
  USING (org_id = current_setting('app.current_org_id')::uuid);
```

Application middleware sets `app.current_org_id` per request based
on the user's Clerk org membership. Once set, every query is
filtered automatically; no need to add `WHERE org_id = ...` in app
code. If middleware forgets, the user sees zero rows — fail safe.

### 2.5 Why these tables (plain English)

- `orgs` + `org_memberships`: who belongs where. Multi-tenant
  foundation. Every other table hangs off `org_id`.
- `projects` + `project_members`: a customer can run multiple
  projects. A user is on one or more projects with a role
  ("mechanical engineer") and owns subsystems ("chassis", "arm").
- `connectors`: a Slack/Drive install. Encrypted tokens.
- `raw_events`: every webhook payload, untouched. So if we mess
  up parsing later we can replay.
- `messages`: parsed Slack/PR/email after we clean up `raw_events`.
  All sources normalise into one table.
- `message_tags`: the router agent's output. One row per message
  saying "this is a decision candidate, urgency=high, mentions
  ECO-178 and AlumWest, affects roles [mech, supply_chain]."
- `documents` + `document_chunks`: PDFs after ingest. Chunks have
  vector embeddings for semantic search.
- `cards`: the **decision/risk/question** atom. The whole product
  is "what cards exist + what do they link to + which ones do you
  care about today."
- `card_sources`: the messages + docs we built this card from.
  Citations live here.
- `edges`: graph relationships. "Card A blocks Card B." "Card C
  depends on Doc D." Used for impact preview + timeline.
- `scores`: a number per (user, message). Pure Python.
- `digests`: the morning briefing for one user, one day.
- `subscriptions` + `notifications`: notification settings + log.
- `audit_log`: every LLM call, every ingest, every notification.
  For compliance + cost tracking + debugging.

---

## 3. API surface

All routes under `/api/v1/`. JSON in, JSON out. Clerk session
cookie for auth. Tenant scoping is automatic via RLS — routes
don't need to pass `org_id`.

### 3.1 Auth + bootstrap

```
GET  /api/v1/me
     → { user_id, org_id, org_name, role, memberships: [...] }
     Used by FE on app load.

POST /api/v1/webhooks/clerk
     → 200
     Clerk fires this when a user/org is created.
     We create matching rows in orgs + org_memberships.
```

### 3.2 Projects

```
GET  /api/v1/projects
     → [{ id, name, current_phase, start_date, milestones, members }]

GET  /api/v1/projects/{id}/today
     → { live_day, phase, phase_concerns, message_count_24h,
         last_digest_at, top_priority_count }
     Powers the dashboard header.

POST /api/v1/projects/{id}/members/{membership_id}/topic-weights
     body { topic, delta }
     → 200
     Called when user thumbs up/down a digest item.
```

### 3.3 Connectors

```
GET  /api/v1/connectors
     → [{ kind, status, installed_by, channels_count, message_count }]

POST /api/v1/connectors/slack/install
     → { redirect_url }
     FE redirects user to Slack OAuth.

GET  /api/v1/connectors/slack/oauth/callback?code=...
     → 302 to /connectors
     Server exchanges code for tokens, stores encrypted.

POST /api/v1/connectors/{id}/channels/{external_id}
     body { ingest: bool }
     → 200
     Toggle per-channel ingest.

POST /api/v1/webhooks/slack
     → 200
     Slack Events API endpoint. Signature verified.
     Persists to raw_events, enqueues route_message Celery task.
```

### 3.4 Messages + cards

```
GET  /api/v1/cards?project_id=...&status=open&kind=decision
     → [{ id, kind, summary, status, sources_count, edges_count,
           confidence, decided_at, updated_at }]

GET  /api/v1/cards/{id}
     → { id, kind, summary, body, status, sources, edges, activity }
     Sources are expanded — full message text + doc chunks.

POST /api/v1/cards/{id}/feedback
     body { useful: bool }
     → 200
     Used to retrain scoring weights.
```

### 3.5 Digests

```
GET  /api/v1/digests/today
     → { id, day_index, phase, content_md, items: [...],
         generated_at }
     User's morning briefing. Read-through cache: serves the
     latest cached digest, kicks off regen if stale.

POST /api/v1/digests/regenerate
     → { job_id }
     Force a fresh regen. SSE will broadcast when done.
```

### 3.6 Subscriptions

```
GET  /api/v1/subscriptions
     → { items: [{ kind, value, enabled }] }

PUT  /api/v1/subscriptions
     body { items: [...] }
     → 200
```

### 3.7 Live updates (SSE)

```
GET  /api/v1/events/stream?project_id=...
     Server-sent events. Each event:
       data: { type: "message_tagged"|"card_created"|"digest_ready",
               payload: {...} }
     Client subscribes; backend's Celery workers publish to Redis
     channel "events:<org_id>"; this endpoint forwards.
```

### 3.8 Health

```
GET  /api/v1/health   → { status: "ok" }
GET  /api/v1/ready    → { db: "ok", redis: "ok", anthropic: "ok" }
```

---

## 4. Backend service breakdown

```
apps/api/src/evercurrent/
├── auth/
│   ├── clerk.py          verify Clerk session
│   └── deps.py           FastAPI deps: get_current_user, get_org
├── tenancy/
│   └── rls.py            SET app.current_org_id on each session
├── db/
│   ├── models.py         SQLAlchemy table classes
│   ├── session.py        async engine + session factory
│   └── repositories/     one file per table family
├── connectors/
│   ├── base.py           Connector protocol
│   └── slack/
│       ├── install.py    OAuth flow
│       ├── events.py     webhook handler → raw_events + enqueue
│       └── backfill.py   one-shot 30d pull
├── routing/
│   ├── router_agent.py   Haiku call: classify + tag
│   └── prompts/route.txt
├── scoring/
│   └── engine.py         pure-Python score function
├── cards/
│   ├── builder.py        message_tags → maybe_create_card
│   └── repository.py
├── digest/
│   ├── agent.py          Sonnet call: draft briefing
│   ├── prompts/digest.txt
│   └── scheduler.py      Celery Beat: per-user 08:00 local
├── notify/
│   ├── slack_deliver.py  chat.postMessage with blocks
│   └── repository.py     notifications table writes
├── jobs/
│   └── celery_tasks.py   route_message, generate_digest,
│                          ingest_document, backfill_slack
├── llm/
│   ├── client.py         AnthropicProvider (only place SDK is imported)
│   └── tiering.py        haiku() vs sonnet() helpers
├── api/
│   └── routers/          one file per route group above
└── main.py               FastAPI app factory + lifespan
```

### Layering rules

- Routes call **services**.
- Services call **repositories** + other services.
- Repositories call **the DB** (or pgvector).
- Never the reverse. No SQL in routes. No HTTP types in services.
- LLM calls only via `llm/client.py`. No `anthropic.AsyncAnthropic()`
  scattered around.

---

## 5. Frontend shape

Built last. Once API is stable, FE is mostly fetching + rendering.

```
apps/web/
├── app/
│   ├── layout.tsx              Clerk provider + theme
│   ├── page.tsx                redirects to /dashboard
│   ├── dashboard/page.tsx      hero screen
│   ├── timeline/page.tsx       (roadmap)
│   ├── decisions/page.tsx      cards list
│   ├── decisions/[id]/page.tsx card detail
│   ├── documents/page.tsx
│   ├── connectors/page.tsx
│   ├── subscriptions/page.tsx
│   └── settings/page.tsx
├── components/
│   ├── cards/                  Knowledge Card UI
│   ├── digest/                 morning briefing renderer
│   └── ui/                     shadcn primitives
├── hooks/
│   ├── use-today.ts            wraps GET /projects/{id}/today
│   ├── use-digest.ts           wraps GET /digests/today + SSE
│   └── use-cards.ts            wraps GET /cards
├── lib/
│   ├── api.ts                  fetch wrapper with Clerk auth
│   ├── types.ts                Zod schemas mirroring API
│   └── sse.ts                  EventSource wrapper
└── stores/
    └── ui.ts                   Zustand: collapsed sections, etc.
```

Server components by default; `"use client"` only for components
that subscribe to SSE or hold local UI state. TanStack Query for all
server state (no `useEffect` for fetching).

---

## 6. End-to-end trace — one Slack message

Tying §1-5 together with one concrete flow:

1. Engineer posts in `#mech-design`.
2. Slack → `POST /api/v1/webhooks/slack`. Middleware verifies HMAC.
3. Handler writes a `raw_events` row, enqueues `route_message` to
   Celery, returns `200`.
4. Celery worker picks up `route_message(raw_event_id)`. Reads the
   raw event. Calls `router_agent.classify(text, thread_context)`
   which calls Haiku via `llm/client.py`.
5. Agent returns `{topic, urgency, entities, affected_roles,
   should_create_card, card_kind}`.
6. Worker writes a `messages` row, a `message_tags` row, and
   (if `should_create_card`) calls `cards.builder.create()` which
   writes `cards` + `card_sources`.
7. Worker calls `scoring.engine.score_for_all_members(message_id)`
   which writes one `scores` row per member of the project.
8. Worker publishes to Redis channel `events:<org_id>`:
   `{type: "message_tagged", payload: {message_id, ...}}`.
9. Browser is subscribed via `GET /api/v1/events/stream`. It
   receives the event, invalidates TanStack Query keys, re-renders.
10. If `urgency=critical` AND any member's score crosses the
    threshold: enqueue `slack_deliver.dm(membership_id, ...)`.

Total: ~2 seconds router → browser update. ~5 seconds router → DM.

---

## 7. What changes when production scale arrives

Documented separately in `docs/PRODUCTION_ROADMAP.md`. Highlights:

- Celery → Temporal for durable multi-step workflows.
- Postgres → CitusData or partitioned Postgres for sharded
  multi-tenancy.
- SSE → WebSocket fanout via dedicated edge service.
- Anthropic direct → routed through an internal LLM gateway with
  budget enforcement + caching.
- Audit log → ClickHouse for analytics.

None of that is needed for the take-home.
