# EverCurrent — Product Requirements Document

## 0. TL;DR

EverCurrent is the **nervous system** for a hardware engineering org.

- **Sources** (read-only): Slack channels, Dropbox folders, GitHub
  PRs, Jira tickets, CAD/PLM later. Org installs once via OAuth.
- **Platform**: stores, links, scores, summarises. Per-user nervous
  system → "what should I know about right now, and why."
- **Surfaces**: web dashboard (primary), Slack DM (push notifications),
  email (fallback).

The agent is **not a chatbot**. It is the autonomous worker behind
every screen: it routes messages, links cross-source events, estimates
impact, drafts the personal briefing. (Interactive chat is roadmap —
the take-home demo ships the autonomous pipeline first.)

---

## 1. Who uses it

Hardware engineering teams: 8–200 people. Roles include mech eng, EE,
firmware, supply chain, QA, PM, procurement. Each member belongs to
**one org**, sees **one or more projects** they're a member of.

Personas:

| Persona               | Cares about                                   | Most-used surface      |
|-----------------------|-----------------------------------------------|------------------------|
| Sarah, mech eng       | thermal failures, ECOs touching her brackets  | morning DM + dashboard |
| Raj, EE               | firmware patches, PCB sourcing                | morning DM + decisions |
| Mei, supply chain     | supplier strikes, lead times, cost changes    | timeline + decisions   |
| David, PM             | risk register, milestone slip, blockers       | dashboard + timeline   |
| Lin, QA               | test reports, anomalies, gate criteria        | documents + cards      |
| Tom, firmware         | open PRs, BMS / motor controller patches      | morning DM + GitHub    |

---

## 2. A day in Sarah's life (plain English)

Sarah is a mechanical engineer at a robot company. Her team is in the
"does it work right?" testing stage — they're running a prototype
robot through stress tests for two weeks before deciding it's ready
to make at higher volume.

**8:00 AM.** Her phone buzzes. Slack DM from EverCurrent:

```
Good morning. Day 4 of testing.

🔴 Top priority — read these first
1. The bracket redesign you proposed (change #178) gets finalised
   today. The electrical engineer already approved his side. You
   still need the supply-chain lead to confirm she can source the
   new aluminum grade. Open the thread →

2. The first sample part from the new aluminum supplier arrived
   at 6:42 AM. Quality team measured it — it passes. So restarting
   the manufacturing run is unblocked. Read →

🟡 Watch-outs — read when you have time
3. A new conversation in the testing channel is about a battery
   safety setting. The firmware engineer's draft code change
   references your heat data. Review when you can.

🔵 FYI — useful background
4. A teammate confirmed a new coating supplier is approved for the
   aluminum grade you're using. That solves a gap you flagged on
   Friday.

🎯 Today's deadline: testing-stage sign-off meeting · Tuesday
🛑 You're not blocking anyone right now.
```

Each line is something **she actually needs to act on or notice**.
None of it is "you got 47 messages in 6 channels." The platform
already filtered the noise.

**8:05 AM.** Sarah taps a link. The web app opens to her
**dashboard** — same items, but expanded with the full context
inline (who said it, in which channel, what the original message
was, who else replied). She gives a thumbs up on item 1 ("yes,
this is the priority level I wanted").

**8:15 AM.** She clicks the **Timeline** tab. A bar chart shows the
project across time: each stage as a coloured band, each big
deadline as a diamond, each design decision as a dot.

She hovers her bracket redesign dot. Red arrows appear: "this change
needs to be done before the testing sign-off on Tuesday." She drags
a "what if?" slider — *what if this change slips 3 days?* — and the
chart shows the ripple: testing sign-off slips, next stage starts 4
days late. She decides she'd better chase the supply-chain lead now.

**8:30 AM.** At the bottom of her dashboard, a card says:

> **⚠ Something you might be missing**
>
> The arm gripper vibrates at a certain speed (4150 RPM). That
> overlaps with the strength rating of the motor mount you
> designed. Priya owns the arm, you own the mount. Three people
> have mentioned this in the last two days. You haven't seen any
> of those messages yet.
>
> Sources: [Priya in #mech-design, Friday], [Raj in #electrical,
> Saturday], [pull request #221]

This is the agent doing its job: noticing that *messages about
something you own* are piling up *without your reaction*. No human
flagged it; the agent inferred it from the data.

Sarah thumbs up. Goes back to work.

**10:30 AM.** She posts in #mech-design: "Looking at the gripper
vibration now — pulling Priya's arm shape." The platform reads her
message, marks the "you might be missing" card as resolved, and
the count on her dashboard drops by one.

She doesn't open EverCurrent again until tomorrow morning. That's
the point — the product earns its keep in **two short visits per
day**, not by demanding she live inside it.

She doesn't open EverCurrent again until tomorrow morning.

---

## 3. Where does data come from

| Source         | What flows in                                       | How                          |
|----------------|-----------------------------------------------------|------------------------------|
| Slack          | channel messages + threads + reactions + file_share | Events API webhook + OAuth   |
| Dropbox        | PDFs (PRD, BOM, ECOs, test reports)                 | Dropbox API + webhooks       |
| GitHub         | PR titles + descriptions + labels + merge events    | GitHub Apps + webhooks       |
| Jira           | issue create / update / status change               | Jira webhooks                |
| Email          | thread import per user (opt-in)                     | Gmail / Outlook OAuth        |
| MES / PLM      | first-article results, ECO status                   | adapter (phase 2)            |
| CAD            | part metadata, BOM lines                            | Onshape / SolidWorks API     |

The org installs these once. Per-source onboarding wizard. Each
connector lives in `connectors/<name>/` and implements the same
Protocol: `oauth_url`, `oauth_callback`, `backfill`, `webhook_handler`,
`pull_latest`.

---

## 4. What the platform actually does (the pipeline)

Inbound event from any source → normalised into a `RawEvent` →
routed by an agent → enriched → scored → surfaced.

```
┌──────────────────────┐
│  Connector webhook    │   Slack/Dropbox/GitHub/Jira/Email
└──────────┬───────────┘
           │  RawEvent { org_id, source, payload, ts }
           ▼
┌──────────────────────┐
│  Router agent (LLM)   │   Haiku-tier: classify
│                       │   { type: message | decision_candidate |
│                       │     document | pr | status_change }
└──────────┬───────────┘
           │
   ┌───────┼────────┬────────────┬──────────┐
   ▼       ▼        ▼            ▼          ▼
[tag]  [decision] [chunk+embed] [link]  [risk/question]
  │       │         │             │          │
  └───────┴────┬────┴─────────────┴──────────┘
               ▼
       ┌──────────────┐
       │   Postgres   │  messages, decisions, documents, edges
       │  + pgvector  │
       └──────┬───────┘
              │   redis.publish("events:<org>", ...)
              ▼
       ┌──────────────┐
       │ Subscribers  │  SSE to web, Slack DM via celery, email
       └──────────────┘

Daily / per-user:
  Digest agent (Sonnet) reads scored items for the user, drafts
  morning briefing → DM via Slack, render in web dashboard.
```

---

## 5. Where the LLM earns its keep (and where it doesn't)

### LLM mandatory

| Use                  | Model        | Why LLM, not rule                                       |
|----------------------|--------------|---------------------------------------------------------|
| Tag message          | Haiku        | natural language → topic / urgency / entities is fuzzy  |
| Extract decision     | Sonnet       | "what was decided + why + who" needs language reasoning |
| Cross-source link    | Sonnet       | "this Slack thread → that PDF section" via semantics    |
| Impact estimation    | Sonnet       | "ECO-178 likely delays DVT exit by N days" needs prior  |
| Personal briefing    | Sonnet       | narrative, second person, citations                     |
| Risk extraction      | Sonnet       | implicit risk in casual conversation                    |
| Chat answer (roadmap)| Sonnet       | open-ended Q over org's data                            |

### LLM NOT needed (rule-based, fast, cheap)

| Use                       | Method                                       |
|---------------------------|----------------------------------------------|
| Per-user scoring          | weighted sum: role + cross-fn + urgency + phase + feedback. Pure Python. |
| Phase concern matching    | substring / synonym map.                     |
| Critical path             | topological sort + earliest-start. Pure Python. |
| Reaction → feedback       | direct DB write: `topic_weights[topic] += delta`. |
| Subscribe / filter        | SQL WHERE.                                   |
| Notification routing      | rule: urgency=critical AND role-match → DM now; else nightly. |

**Net:** LLM is the autonomous *worker* for understanding +
linking + writing. Scoring + filtering + delivery are pure Python.
Together they're agentic — autonomous decisions across heterogeneous
sources, with deterministic delivery rules layered on top.

---

## 6. Why an agent (not just an LLM pipeline)

An "LLM pipeline" = fixed steps, one call per step, deterministic
graph. Good for batch.

An "agent" = decides which step + which tool + how many iterations.

**Take-home scope (built):**

1. **Router agent (per message).** Inbound event → agent decides:
   "is this a decision? a status update? a question? noise?" Takes
   different downstream paths. Tools: classify, get-thread-context,
   get-user-context. Haiku tier.
2. **Digest agent (per user, nightly).** Reads pre-scored top-N items,
   drafts the morning briefing with citations. Sonnet tier. Hero
   feature of the demo.
3. **Linker agent (per new Card)** — stretch goal. Sonnet calls
   `search_documents`, `search_messages`, `query_decisions` to build
   cross-source edges.

**Roadmap (not in take-home demo):**

4. **Chat agent (on dashboard).** User asks an open question → agent
   uses 6+ tools to compose grounded answer with citations. Bumped to
   roadmap because tool registry + RAG re-rank + streaming UI +
   citation rendering = ~3 days, and Router + Digest already prove the
   "autonomous understanding + personalized output" thesis.
5. **Phase agent.** Reads open decisions + risks → judges "ready for
   DVT exit?" with gap list.
6. **Personalizer agent.** Weekly cron; re-weights `topic_weights`
   from feedback patterns.

Without agents you'd hand-code these as if-trees with O(N) branches.
With agents you get adaptive behaviour out of the box.

---

## 7. Every screen

### 7.1 Authenticated shell

```
┌───────────────────────────────────────────────────────────────────┐
│  EverCurrent       Acme Robotics ▾    Sarah Chen (mech)   ⚙ 🔔 │
├────────────────┬──────────────────────────────────────────────────┤
│ • Dashboard    │                                                  │
│   Timeline     │                                                  │
│   Decisions    │   [main]                                         │
│   Documents    │                                                  │
│   Connectors   │                                                  │
│   ─────────    │                                                  │
│   Subscriptions│                                                  │
│   Audit        │                                                  │
│   Settings     │                                                  │
│                │                                                  │
│   Ask ✨ soon  │                                                  │
└────────────────┴──────────────────────────────────────────────────┘
```

Top right: org switcher (if member of multiple), user menu, settings,
notification bell.

### 7.2 Dashboard (Home)

Heart of the product. The "morning briefing made interactive."

```
┌───────────────────────────────────────────────────────────────────┐
│  Mon Jun 8 · DVT · day 4                          [Regenerate ↻] │
├───────────────────────────────────────────────────────────────────┤
│  🔴 TOP PRIORITY                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ ECO-178 fast-track closes today. Mei sign-off pending.      │ │
│  │ #mech-design · David · 06:14 · 4 sources linked            │ │
│  │ Why this matters: you authored ECO-178; blocks DVT exit.   │ │
│  │ [👍] [👎] [View thread] [Open card]                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  🟡 WATCH-OUTS                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ AlumWest first-article landed. Pass. Re-fab cleared.        │ │
│  │ #qa-testing · Lin · 06:42                                   │ │
│  │ Why: tolerance ±0.07mm < spec ±0.10mm. Action: review res.  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  🔵 FYI                                                           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Carlos qualified PrecisionCoat for AL-7075 finishing.       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ─────────────────────────                                       │
│  ⚠ You're not paying attention to:                               │
│   Gripper resonance band (4150 RPM) may collide with motor       │
│   mount torque spec. Priya owns arm; you own mount. [Open]       │
└───────────────────────────────────────────────────────────────────┘
```

Each card shows: source, author, when, why-this-matters (one
sentence from the LLM), inline feedback buttons. "Open card" leads to
the full **Knowledge Card** (see 7.4). The bottom "not paying
attention" block is the agent's proactive surface — flagged based on
mentions of your owned subsystems that you haven't reacted to.

### 7.3 Timeline (Gantt)

```
                Jun 1   Jun 3   Jun 5   Jun 7   Jun 9   Jun 11
EVT      ▓▓▓▓▓▓▓▓▓▓░░░
DVT                ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓◆━━━━━━░░░░░
PVT                                ◆ECO-178           ▓▓▓▓◆
MP                                                       ◆━━━

Filter: ▣ owned by me  □ all decisions  ▣ phase-relevant docs
```

- Horizontal bands = phases (active phase highlighted).
- Diamonds = milestones (DVT exit, PVT kickoff, MP).
- Dots = decisions plotted at `decided_at`.
- Arrows = agent-inferred dependencies (decision → milestone).
- Hover a dot → side panel shows decision + downstream impact.
- Drag a milestone → live what-if recompute via SSE.
- Critical-path edges highlighted in red.

### 7.4 Decisions

```
┌───────────────────────────────────────────────────────────────────┐
│  Decisions               filter: ▣ affects me  ▣ open + decided   │
├───────────────────────────────────────────────────────────────────┤
│  ◉ Switch BRK-A1 from AL-6063-T5 to AL-7075-T6 (ECO-178)         │
│  status: decided · confidence: 0.95 · decided_by: Sarah           │
│  affects: chassis, supply_chain · 4 source msgs · 1 PDF · 1 PR    │
│  ↓ blocks: AlumWest first article (cleared Jun 8)                │
│  ↓ blocks: DVT exit (Tue Jun 9)                                  │
│  [Open card]                                                      │
├───────────────────────────────────────────────────────────────────┤
│  ◉ BMS hysteresis tighten 8°C → 5°C (PR #221)                    │
│  ...                                                              │
└───────────────────────────────────────────────────────────────────┘
```

Filter "affects me" uses owned_subsystems intersection.

### 7.5 Knowledge Card (the atomic unit)

Click any decision / risk / open question → opens the Card.

```
┌───────────────────────────────────────────────────────────────────┐
│  ECO-178 · Switch BRK-A1 to AL-7075-T6                            │
├───────────────────────────────────────────────────────────────────┤
│  ── Summary ──                                                    │
│  Change chassis bracket material from AL-6063-T5 to AL-7075-T6   │
│  in two specific high-flux regions to fix thermal margin.        │
│                                                                   │
│  ── Why ──                                                        │
│  Thermal cycling failed at unit 7 at chassis temp 91°C (spec 85). │
│  Bracket boss face localised heat; FEA confirmed conduction       │
│  limit; material change cheaper than geometry change.            │
│                                                                   │
│  ── Sources ──                                                    │
│  📨 #mech-design · Sarah · Jun 6 06:14                            │
│  📨 #qa-testing · Lin · Jun 6 09:14 (thermal failure orig)        │
│  📄 PRD §3.2 Dropbox — torque spec                                │
│  📄 BOM rev C — AL-7075-T6 line                                   │
│  🔗 PR #214 firmware retry count                                  │
│                                                                   │
│  ── Impact ──                                                     │
│  ▶ blocks: DVT exit (Tue Jun 9)                                  │
│  ▶ touches: chassis, supply_chain                                │
│  ▶ depends on: AlumWest qualification (✓ cleared Jun 8)          │
│                                                                   │
│  ── Activity ──                                                   │
│  Jun 6 — Sarah drafted ECO                                       │
│  Jun 6 — Raj signed off (EMC unaffected)                         │
│  Jun 7 — Mei sourcing path approved                              │
│  Jun 8 — AlumWest FAI cleared                                    │
│  Jun 8 06:14 — David fast-track approval pending Mei (you)       │
│                                                                   │
│  [👍 useful for me] [💬 add comment] [📌 pin to home]            │
└───────────────────────────────────────────────────────────────────┘
```

Knowledge Cards are first-class. Every decision, risk, and open
question is a Card. Cards are also Slack threads (the agent creates
one in `#general` per Card; replies sync back). Searchable via Chat.

### 7.6 Documents

```
filter by phase: [DVT] ▣  · by kind: [PRD] [BOM] [ECO log] [Test]
                       │
   ┌─────────────────┐│┌─────────────────┐┌─────────────────┐
   │ PRD             │││ BOM (rev C)     ││ Thermal report  │
   │ active: all     │││ active: DVT…MP  ││ active: DVT,PVT │
   │ 12 sections     │││ 24 lines        ││ 8 anomalies     │
   │ 4.2KB excerpt   │││ 2.1KB excerpt   ││ 1.8KB excerpt   │
   └─────────────────┘│└─────────────────┘└─────────────────┘
                       │
   PDFs ingested from Dropbox auto-flow here. Phase tag editable.
```

Click a document → embedded viewer with section navigation. Hover any
section → "linked to" panel shows decisions / threads / cards
referencing it.

### 7.7 Chat (roadmap, not in take-home)

Open-question interface over org data. Tools: `search_messages`,
`search_documents`, `query_decisions`, `get_user_context`,
`get_thread_context`, `get_project_state`. Inline tool-call inspector.
Streamed answer with citations. Per-user conversation history.

**Why deferred:** Router + Digest already prove the agentic thesis for
the demo. Chat needs tool registry, RAG re-rank, streaming SSE on
query, citation rendering, transcript persistence — ~3 days extra. Cut
from take-home; first item on the post-submission roadmap.

Sidebar shows "Ask ✨ soon" disabled link as a teaser during the demo.

### 7.8 Connectors

```
┌───────────────────────────────────────────────────────────────────┐
│  Sources                                                          │
├───────────────────────────────────────────────────────────────────┤
│  Slack          ✓ connected by David · 5 channels · 12k messages │
│                  [pause] [pick channels] [remove]                │
│  Dropbox        ✓ connected by Mei · 2 folders · 47 docs         │
│                  [pause] [pick folders] [remove]                 │
│  GitHub         ⊘ not connected                  [Connect →]     │
│  Jira           ⊘ not connected                  [Connect →]     │
│  Email (Sarah)  ✓ Gmail · 30d backfill                           │
│  Onshape        soon                                              │
└───────────────────────────────────────────────────────────────────┘
```

Org admins manage org-wide connectors (Slack, Dropbox, GitHub, Jira).
Users manage personal connectors (Email, Calendar).

### 7.9 Subscriptions

```
What you get DM'd / emailed:
  ▣ morning digest at 08:00 (Slack DM)  edit
  ▣ urgent items immediately (Slack DM)  edit
  □ weekly summary (email)
  ▣ items where you're @mentioned (Slack DM)
  ▣ decisions affecting subsystems you own (Slack DM)

Topics you follow (boost in scoring):
  + thermal margin     + ECO velocity
  + chassis            + AL-7075

Topics you mute:
  – firmware (low interest)
```

This is how feedback weights become visible. Plus power-user filters.

### 7.10 Audit

```
Every LLM call. Every connector ingest. Every notification sent.
Searchable. Exportable for SOC 2.

Jun 7 14:02  Sonnet  digest_agent  user=Sarah  tokens=1532/487
Jun 7 14:02  Haiku   route_message msg=Sj8x    tokens=412/89
Jun 7 14:01  Slack   ingest_event  ts=...      bytes=2400
```

### 7.11 Settings

Org level: name, billing, plan, ITAR flag, region.
User level: timezone, notification windows (quiet hours), theme.

---

## 8. Notifications design

| Trigger                                       | Channel        | Default     |
|-----------------------------------------------|----------------|-------------|
| Morning digest                                | Slack DM       | 08:00 local |
| Critical urgency + role/owns match            | Slack DM       | immediate   |
| @mention in a watched channel                 | Slack DM       | immediate   |
| New decision affecting your subsystem         | Slack DM       | hourly batch|
| Weekly summary                                | Email (Resend) | Sun 18:00   |
| Anomaly nudge                                 | Slack DM       | as detected |

Users control all of this in Subscriptions. Quiet hours respected.

---

## 9. Data model (additions to current schema)

```sql
-- Multi-tenancy
orgs                  (id, clerk_org_id UNIQUE, name, plan, itar, region, created_at)
org_memberships       (id, org_id, clerk_user_id, slack_user_id, role, timezone, locale)

-- Connectors
connectors            (id, org_id, kind, status, scope, credentials_kms_arn, installed_by, installed_at)
connector_channels    (id, connector_id, external_id, name, ingest BOOLEAN)

-- Knowledge cards
cards                 (id, org_id, project_id, kind, summary, body, status, owner_user_id, created_at)
card_sources          (id, card_id, source_kind, source_ref) -- message / doc / PR / etc

-- Cross-source edges
edges                 (id, org_id, from_kind, from_id, to_kind, to_id, edge_type, confidence, inferred_by)

-- Personal subscriptions
subscriptions         (id, user_id, kind, value) -- topic, channel, user, decision_keyword
notification_prefs    (id, user_id, channel, when, quiet_start, quiet_end)

-- Notifications log
notifications         (id, user_id, kind, payload, sent_at, delivered_via, opened_at, clicked_at)
```

All tenant-scoped tables get `org_id` FK + Postgres RLS:
`USING (org_id = current_setting('app.current_org_id')::uuid)`.

---

## 10. Backend shape (additions)

```
apps/api/src/evercurrent/
├── auth/
│   ├── clerk.py             Clerk SDK + webhook handlers
│   └── deps.py              get_current_user, get_current_org
├── tenancy/
│   ├── rls.py               set app.current_org_id per request
│   └── middleware.py
├── connectors/
│   ├── base.py              Connector Protocol
│   ├── slack/{install,oauth,events,backfill,deliver}.py
│   ├── drive/{install,pull,push}.py
│   ├── github/{install,webhook}.py
│   ├── jira/{install,webhook}.py
│   └── email/{gmail,outlook}.py
├── routing/
│   └── router_agent.py      classifier (Haiku tier)
├── linking/
│   └── linker_agent.py      cross-source edge builder (Sonnet)
├── impact/
│   └── critical_path.py     pure-Python topological + earliest-start
├── cards/
│   ├── builder.py           materialise decisions/risks/questions
│   └── slack_sync.py        keep Card ↔ Slack thread mirrored
├── notify/
│   ├── digest_agent.py      per-user morning brief (Sonnet)
│   ├── slack_deliver.py     chat.postMessage with blocks
│   └── email_deliver.py     Resend
└── (existing modules stay)
```

---

## 11. Phased build

| Phase | Scope                                                      | Days | Take-home? |
|-------|------------------------------------------------------------|------|------------|
| 1     | Clerk auth + orgs + memberships + RLS                      | 1-2  | ✓          |
| 2     | Slack OAuth + Events ingest + backfill                     | 2-3  | ✓          |
| 3     | Router agent + per-message enrichment                      | 1    | ✓          |
| 4     | Dropbox connector (PDFs) + per-doc phase tag               | 1    | ✓          |
| 5     | Knowledge Cards + digest agent + per-user briefing         | 2    | ✓          |
| 6     | Dashboard rebuild (cards-first, not days-of-week)          | 1    | ✓          |
| 7     | Slack DM delivery + Subscriptions + quiet hours            | 1    | ✓          |
| 8     | Linker agent + edges                                       | 1.5  | stretch    |
| 9     | Timeline (Gantt) + critical path                           | 2    | stretch    |
| 10    | Chat agent + tool inspector UI                             | 3    | roadmap    |
| 11    | Email (Resend) + weekly summary                            | 0.5  | roadmap    |
| 12    | GitHub + Jira connectors                                   | 1    | roadmap    |
| 13    | Phase agent + Personalizer + Audit page                    | 1.5  | roadmap    |
| 14    | Polish + demo video + reviewer doc                         | 1    | ✓          |

Take-home submission scope (~5-7 days): **Phases 1-7 + 14.** Demo
product: real Slack workspace ingested, router agent tags every
message, Cards generated, dashboard cards-first, digest agent ships
morning brief via Slack DM. Linker + Timeline = stretch goals if time.

Roadmap framing in interview: "I scoped ruthlessly. The autonomous
pipeline ships first; Chat / Timeline / extra connectors are the
visible next milestones."

---

## 12. What's deliberately NOT in scope (yet)

**Cut from take-home, on roadmap:**

- Chat agent (interactive Q&A) — biggest single feature deferred
- Timeline / Gantt + critical-path what-if
- Linker agent for cross-source edges (if not reached as stretch)
- Phase agent ("ready for DVT exit?")
- Personalizer agent (weekly feedback re-weighting)
- GitHub + Jira + Email connectors
- Audit page

**Not on roadmap at all (yet):**

- CAD ingestion (Onshape API integration)
- MES adapter
- Mobile app
- White-label
- A/B prompt routing
- Federated cross-org knowledge ("similar projects bit us before")
- Voice digest / TTS
- Auto-PR drafting

---

## 13. Success metrics

| Metric                                       | Target (90 days) |
|----------------------------------------------|------------------|
| DAU / installed seats                        | > 60%            |
| Morning digest open rate                     | > 70%            |
| Median time-to-react on critical alerts      | < 15 min         |
| Digest items thumbs-upped per user / week    | > 5              |
| Chat answers rated useful                    | > 80%            |
| Connectors per org                           | ≥ 3              |
| LLM cost / DAU / month                       | < $3             |

---

## 14. Risks

- **Connector breakage.** Slack changes API → ingestion stops.
  Mitigation: integration tests per connector, status page, manual
  resync button.
- **LLM cost runaway.** Per-org budget alarm. Fall back to heuristic
  generator above threshold.
- **Privacy / ITAR.** Tenant flag → regional Anthropic endpoint +
  on-prem LLM option. PII redaction step before LLM.
- **Notification fatigue.** Quiet hours default. Throttle: max 1
  critical DM / hour unless user opts out.
- **"Just another digest tool."** Differentiator is the Card model +
  cross-source linking + critical-path impact preview, not the
  morning email.
