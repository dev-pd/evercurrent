# EverCurrent — Demo Script

A 10-minute live walkthrough. Six sections, ~2 minutes each. Italicised
notes are what to say; non-italicised are what to click. Rehearse the
clicks once; the words flex.

Before you start:
- `make up-monitor` — stack including Grafana
- `make migrate` — schema in place
- Two browser tabs open: `localhost:3000/dashboard` impersonated as
  Sarah, and `localhost:3001` for Grafana
- A terminal tail on `make logs-pretty` ready to scroll
- Slack workspace with the bot installed; phone open to
  `#mech-design`

## Section 1 — System design (2 min)

*"Hardware engineering teams have knowledge scattered across Slack,
PDFs, GitHub, Jira. An engineer who owns a chassis bracket needs to
know — today — that the aluminum supplier is on strike, that the
firmware team's BMS thermal model assumes the old alloy, and that the
phase gate review is Friday. The job EverCurrent does is not 'send a
digest.' It is to route every inbound event, store it, score it per
person, and surface it where they already are."*

Open `docs/SYSTEM_DESIGN.md` to the §1 diagram and walk left to right:

- **Browser** — Next.js App Router + SSE for live updates.
- **FastAPI** — middleware verifies Auth0 token, sets
  `app.current_org_id` for Postgres RLS, so every query is auto-scoped.
- **Postgres 17 + pgvector** — single store. Messages, message_tags,
  cards, edges, document chunks with 512-dim embeddings.
- **Redis** — Celery broker + pub/sub for SSE fanout.
- **Celery + Beat** — background jobs (`route_message`,
  `generate_digest`, `ingest_doc`) and cron (per-minute scheduler that
  fires digests at user-local 08:00).
- **Anthropic** — Haiku for the Router agent, Sonnet for the Digest
  agent and Card writer. **Voyage** for embeddings.

*"Two agents, not one mega-agent. Router is per-message, has to be
fast and cheap — Haiku. Digest is per-user per-morning, writes
narrative — Sonnet. The ADR for that split is in
`docs/DECISIONS.md` ADR-008."*

## Section 2 — Live Slack ingest (2 min)

*"The reviewer can see this themselves. I post a message from my phone
into a real Slack workspace. The Router agent classifies it. A Card
gets created. The dashboard updates over SSE in under a second.
Nothing is faked."*

1. From phone, post in `#mech-design`:
   > "Decided: switching BRK-A1 to AL-7075-T6. ECO-178 drafted."
2. Switch to the terminal:
   - `make logs-pretty` shows the `slack.event.received` line for the
     raw_event row.
   - Then `router.classify` with the structured JSON output:
     `topic=eco`, `urgency=high`, `entities=[BRK-A1, AL-7075-T6,
     ECO-178]`, `should_create_card=true`.
   - Then `cards.build` with the new card_id.
3. Switch to the dashboard tab. Without refresh, a new "Top priority"
   Card slides in.
4. Click the Card. Show the structured body, the linked source
   message, the affected subsystems.

*"That is the whole inbound loop. Slack webhook -> raw_events row ->
Celery task -> Router agent -> message + message_tags rows -> Cards
builder -> SSE event on `events:<org_id>` -> the browser's TanStack
Query invalidates and the FE re-renders."*

## Section 3 — Morning digest (2 min)

*"The Digest agent is the product's hero feature. It writes Sarah's
morning briefing — three sections, prioritised, cited back to the
source. Sonnet, not Haiku, because the writing matters."*

1. On the dashboard, click "Regenerate digest."
2. Switch to the terminal, show the prompt construction trace:
   - `digest.prompt.rendered` — the Jinja-rendered context: member
     profile, project snapshot, top-20 scored items, open Cards.
   - `llm.complete` line with the Sonnet model name, input tokens,
     output tokens, latency.
3. Back to the dashboard. The digest renders with three sections:
   - **Top priority** — ECO-178 finalisation
   - **Watch-outs** — gripper resonance band
   - **FYI** — PrecisionCoat qualified
4. Click any item to expand. The citation pill `[msg:<uuid>]` resolves
   to the original Slack message text + author + channel.

*"Every cited id has to exist in the input set. The agent's output is
validated against `DigestDraft` (Pydantic strict), then the citation
filter drops any UUID the model invented. The digest in the dashboard
is the persisted `digests` row, keyed `(member, day_index)` unique."*

## Section 4 — PDF flow (2 min)

*"Drive is the other inbound. PDFs become chunked vectors in
pgvector. The same Cards pipeline reads them — an ECO PDF auto-creates
a Card."*

1. Open a terminal. `cp seed_data/sample_pdfs/eco_178.pdf
   /tmp/drop_zone/` (the mock-Drive watch directory).
2. Run `uv run python -m apps.api.scripts.seed_drive_mock` (or whatever
   the scripted ingest entry is).
3. Watch the log:
   - `drive.event.received` — file detected.
   - `drive.pdf.extracted` — PyMuPDF block extraction; page + section
     boundaries logged.
   - `rag.embed.batch` — Voyage call with the chunks.
   - `cards.build` — Sonnet drafts a Card from the ECO summary block.
4. Switch to the dashboard. A new Card appears under "Top priority"
   with the ECO summary.

*"The pdf chunking strategy is in `rag/chunker.py` — preserve
section paths, recursive split at 800 tokens with 100-token overlap.
The Voyage embedder is at `rag/embedder.py`. The doc and chunks
land via the `index_document` task in `rag/indexer.py`."*

## Section 5 — Code tour (2 min)

*"Eight files, opened in pipeline order. By file 8 you understand the
whole inbound pipeline."*

Open each in the editor for ~12 seconds; talk about the layering:

1. `apps/api/src/evercurrent/main.py` — FastAPI factory + lifespan.
   *Notice the routers are imported here, not in routes themselves.*
2. `apps/api/src/evercurrent/auth/deps.py` — Auth0 verify +
   `get_current_org_membership` sets the RLS context. *Failure is
   safe: forgetting the dep means the user sees zero rows.*
3. `apps/api/src/evercurrent/connectors/slack/events.py` — webhook
   handler, HMAC verify, dedupe, enqueue the Celery task.
4. `apps/api/src/evercurrent/routing/router_agent.py` — the Haiku
   classify call. *Notice the single retry on schema drift, then the
   uncategorised fallback. No infinite loops.*
5. `apps/api/src/evercurrent/jobs/tasks/route_message.py` — the
   Celery task wrapper that orchestrates router + scoring + Cards.
6. `apps/api/src/evercurrent/cards/builder.py` + the
   `cards/prompts/draft_card.txt` system prompt. *Sonnet, structured
   output via Pydantic strict.*
7. `apps/api/src/evercurrent/digest/agent.py` + `digest/scheduler.py`
   — the Sonnet agent and the per-minute Beat scan that fires user
   digests at local 08:00.
8. `apps/api/src/evercurrent/notify/quiet_hours.py` +
   `notify/block_kit.py` — when to DM, how to format. Pure Python,
   timezone math.
9. `apps/api/src/evercurrent/mcp/tools/search_messages.py` — one
   example of the MCP tool layer. *The agents are MCP clients in this
   build; moving the server out-of-process is a config change.*

*"Layering rule: routes -> services -> repositories -> DB. No SQL in
routes. No HTTP types in services. LLM only via `llm/client.py`. If a
file violates the rule, it's a bug. AGENTS.md §5 is the canonical
list."*

`docs/CODE_TOUR.md` is the same list with file:line ranges and
narrative for self-study.

## Section 6 — Observability (optional 1 min)

*"If a reviewer asks about production posture, this is the answer."*

1. Open `localhost:3001` (Grafana).
2. Three panels worth showing:
   - **Request rate + p99 latency** on `/api/v1/*`.
   - **LLM call count by tier + token cost** (computed from the
     `llm.complete` structlog event).
   - **Background queue depth** (Celery to Redis pub).
3. *"All structlog events render in Loki. Promtail tails the
   docker-compose log driver. No bespoke per-service code."*

## After the demo — open for questions

Have these tabs ready:

- `docs/DECISIONS.md` — every architectural choice with rationale.
- `docs/PRODUCTION_ROADMAP.md` — the scale-out story.
- `docs/EVAL_BASELINE.md` — the four eval numbers.
- `docs/AGENT_VS_WORKFLOW.md` — what the agent actually decides.

*Most-likely grill questions are pre-answered in `docs/DECISIONS.md`.*
