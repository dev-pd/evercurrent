# Agent vs workflow — what does the agent actually automate

You asked the right question. Most products that say "agent" are
running workflows + one LLM call somewhere. We need to be honest
about which is which.

## Definitions

**Workflow** = deterministic graph of steps. Same input → same path.
Engine guarantees retry, ordering, persistence. Tools: Celery beat,
Temporal, Airflow.

**Agent** = autonomous LLM that, given input + a toolbox, decides
*which* tools to call, *in what order*, *how many iterations*, and
*when to stop*. Output is non-deterministic and adaptive.

Both coexist. Workflows orchestrate at the top level; agents run
inside specific steps where the question is "what should I do with
this thing?" instead of "do these 5 things in order."

---

## End-to-end trace: one Slack message

Mei posts in `#supply-chain`:

> "ExtruCo strike confirmed — pulling AlumWest forward. Need a
> tolerance trial lot by Monday. ECO-178 looks unaffected from my
> side; happy to sign off once Lin confirms FAI cleared."

Watch where workflow runs, where agent runs.

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Slack Events API → POST /slack/events                            │
│    WORKFLOW. Signature verify, dedup by ts, persist raw event.      │
│    Pure code. No LLM. ~5ms.                                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼ enqueue Celery task: route_event
┌─────────────────────────────────────────────────────────────────────┐
│ 2. ROUTER AGENT (Haiku)                                             │
│    Input: { text, channel, author, thread_root, attachments }       │
│    Tools: classify(), get_thread_context(), get_user_context()      │
│    Agent decides:                                                   │
│      - what kind of event is this?                                  │
│      - does it need thread context to interpret?                    │
│      - does it imply a decision was made?                           │
│      - which downstream tasks to enqueue?                           │
│                                                                     │
│    Trace for this message:                                          │
│      iter 1: classify() → "status_update + decision_candidate +     │
│                            cross_functional_dependency"             │
│      iter 2: get_thread_context() → fetches AlumWest backlog        │
│      iter 3: returns { actions: [                                   │
│        tag_message(topic=supply_chain_disruption, urgency=high,     │
│                    entities=[ExtruCo, AlumWest, ECO-178],           │
│                    affected_roles=[supply_chain, mech_eng, qa]),    │
│        link_to_card(card="ECO-178", as=signoff_pending_lin),        │
│        bump_owner_attention(user_id=lin_id, reason="Mei waiting"),  │
│        nudge_user_immediate(user_id=sarah_id,                       │
│                              reason="ECO-178 you authored")         │
│      ] }                                                            │
│                                                                     │
│    WITHOUT agent: regex on "ECO-NNN" + keyword list + role table.   │
│    Misses: "happy to sign off" = soft commitment.                   │
│    Misses: "looks unaffected from my side" = scoped scope.          │
│    Misses: tolerance + supplier strike co-occurrence importance.    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┬────────────────┐
                ▼              ▼              ▼                ▼
        [tag_message]   [link_to_card]  [bump_attention]  [nudge_user]
         WORKFLOW         WORKFLOW         WORKFLOW         WORKFLOW
         pure SQL         pure SQL         pure SQL        Slack DM
                          via edges
                               │
                               ▼ message_tagged event published
┌─────────────────────────────────────────────────────────────────────┐
│ 3. SCORING (pure Python, NOT agent)                                 │
│    For every active user of this org:                               │
│      score = role_match + cross_fn + urgency + phase + feedback     │
│    No LLM. < 1ms. Stored as denormalised view for fast reads.       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. URGENT PATH (rule, NOT agent)                                    │
│    For users where score > THRESHOLD AND urgency == critical:       │
│      enqueue immediate Slack DM                                     │
│    For Lin: matches. DM enqueued. (She owns thermal testing.)       │
│    For Sarah: matches via affected_roles. DM enqueued via           │
│                bump_attention.                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. NIGHTLY DIGEST (workflow + agent inside)                         │
│    08:00 in Mei's timezone, Celery beat fires digest_agent for Mei. │
│                                                                     │
│    DIGEST AGENT (Sonnet)                                            │
│    Input: top-N scored items for Mei, her profile, project phase,   │
│           prior 3 days' digests for continuity                      │
│    Tools: search_messages, get_thread_context, get_user_context,    │
│           query_decisions, search_documents                         │
│    Agent decides:                                                   │
│      - which items to lead with                                     │
│      - which need expansion vs one-liner                            │
│      - which carry forward from yesterday vs new                    │
│      - whether to flag "things you're missing"                      │
│      - tone + voice + length                                        │
│                                                                     │
│    Output: markdown briefing, cited.                                │
│                                                                     │
│    WITHOUT agent: template engine. Generic. Bad copy. No "you're   │
│    not paying attention to" insight. No tone calibration.          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Every decision point — agent or not?

| Decision                                          | Agent? | Why                                                                |
|---------------------------------------------------|--------|--------------------------------------------------------------------|
| Verify Slack signature                            | no     | crypto, deterministic                                              |
| Dedup by Slack `ts`                               | no     | unique constraint                                                  |
| What kind of event is this?                       | **yes**| natural language → category. Rules brittle.                        |
| Does this message imply a decision?               | **yes**| "happy to sign off" vs "we should consider X" — only LLM reads tone|
| Which entities are mentioned?                     | **yes**| NER + part-number patterns + new entities. Hybrid; LLM wins.       |
| Which roles care?                                 | **yes**| context-dependent. "supplier strike" hits supply_chain *and* anyone whose subsystem depends on the supplier. |
| Score per user                                    | no     | additive formula. Pure Python.                                     |
| Urgent → DM now? Quiet hours apply?               | no     | rule + per-user prefs                                              |
| Link this message to which Card?                  | **yes**| semantic similarity + sometimes new card needed                    |
| Should this become a new Card?                    | **yes**| LLM judges "is this a decision worth a card or a status update?"   |
| Draft Card body                                   | **yes**| LLM writes summary, rationale, impact                              |
| Extract dependency edges                          | **yes**| "blocks X", "depends on Y" implicit in language                    |
| Critical path computation                         | no     | topological sort on edges agent built                              |
| Phase auto-suggest ("DVT exit ready?")            | **yes**| reads decision statuses + open risks + judges readiness            |
| Morning briefing copy                             | **yes**| narrative, citations, second person                                |
| Notification routing (DM vs email vs in-app)      | no     | user prefs + urgency rule                                          |
| Quiet hours enforcement                           | no     | timezone math                                                      |
| Chat answer over org data                         | **yes**| multi-tool reasoning, citations                                    |
| Document chunk + embed                            | no     | deterministic chunker + Voyage call                                |
| RAG retrieval (vector search)                     | no     | pgvector ANN. Pure DB.                                             |
| RAG re-ranking / answer composition               | **yes**| LLM composes from retrieved chunks                                 |
| Anomaly nudge ("you should look at X")            | **yes**| pattern detection from mentions you haven't reacted to             |

**Tally:** 12 agent decisions + 9 deterministic. Agent is doing
the *understanding* + *writing*. Workflow is doing the *plumbing* +
*delivery*.

---

## What if there were NO agent?

Same product, agent stripped:

| Feature                | Without agent                                                    |
|------------------------|------------------------------------------------------------------|
| Message tagging        | regex on keywords. Catches obvious ECOs; misses tone, intent.    |
| Decision extraction    | trigger-word rules. False positives ("we should consider…").     |
| Cross-source linking   | manual entry only. User has to tell us "this is related to ECO-178." |
| Impact estimation      | gone. No "blocks DVT exit" inference.                            |
| Personal briefing      | template: "Top 5 messages by score". Generic, no voice.          |
| Chat                   | gone. Replace with keyword search box.                           |
| Anomaly nudge          | gone.                                                            |
| Phase auto-suggest     | gone.                                                            |

What's left = a tagged Slack archive with a scoring view. That's the
2018-era "Slack analytics" product. Loses to the moment.

The **agent is what makes it 2026** — autonomous understanding +
linking + writing that adapts to the org's vocabulary without
hand-coded rules.

---

## Temporal vs Celery vs agent

Three different things, often confused.

| Tool      | What it does                                                      |
|-----------|-------------------------------------------------------------------|
| Celery    | Job queue. "Run this function in worker process, retry on fail."  |
| Temporal  | Durable workflow engine. "Run this 5-step process, survive crashes, replay state on resume." |
| Agent     | LLM that picks tools / steps autonomously inside ONE workflow step.|

**They coexist.** Pattern:

```
Temporal workflow "process_inbound_message":
  step 1: persist raw event       (deterministic — pure code)
  step 2: route via agent         (calls Router Agent)
  step 3: enrich (tag + entities) (deterministic — Haiku call from agent's plan)
  step 4: score per user          (deterministic — pure Python)
  step 5: maybe enqueue DM        (rule)
  step 6: link to Card via agent  (calls Linker Agent)
```

Temporal gives durability: if step 4 crashes, Temporal resumes from
step 3's output. Agent gives intelligence: step 2 and step 6 use LLM
to decide what step 3-5 should look like.

**Current build uses Celery + Beat**, not Temporal. Reason: simpler
for one-week scope, fewer moving pieces. Production: move durable
workflows (the multi-step "process message" or "advance phase") to
Temporal. Per-step Celery tasks for fan-out (digest for 200 users
at 08:00 local — 200 tiny tasks, Celery is fine).

Roadmap migration: `docs/PRODUCTION_ROADMAP.md` §"Scaling".

---

## Agent inputs — what does it actually read?

Concrete answer to "does the agent check PDFs / records?":

The **router agent** (per message) reads:
- the message text
- thread context (parent + replies) if relevant
- the author's profile (role, owned subsystems)
- the active project phase + phase concerns

It does **NOT** read full PDFs or the message corpus. Too much
context, too slow, too expensive.

The **chat agent** (on dashboard) DOES read across everything via
RAG tools:
- `search_documents` → pgvector ANN over chunked PDFs (sees 5
  chunks, ~5 KB each, on demand)
- `search_messages` → full-text + tag filter
- `query_decisions` → structured query
- `get_user_context`, `get_project_state` → DB lookup

It composes an answer using only what it pulled. Citations always
shown.

The **linker agent** (per new decision) reads:
- the decision summary
- top-K semantically similar past decisions
- top-K semantically similar PDF chunks
- the project's milestone list

Builds edges between them. Output: a list of `{from, to, type,
confidence}` triples persisted as graph rows.

The **digest agent** (per user per morning) reads:
- the top-N scored items for that user (already filtered)
- the user's profile + prior 3 days' digests for continuity
- the project's open critical-path nodes

Drafts the briefing. Each item it cites comes from the input set;
no surprise fetching.

---

## Impact of the agent — measurable, not hand-wavy

Agent earns its place if these are achievable without hand-tuned
rules per org:

| Metric                                              | Target |
|-----------------------------------------------------|--------|
| Tag accuracy on novel topics (no rule update)       | > 90%  |
| Decision precision (judge eval)                     | > 0.85 |
| Decision recall                                     | > 0.70 |
| Cross-source edge precision                         | > 0.80 |
| Digest items rated useful by user                   | > 80%  |
| Chat answers cited correctly                        | > 90%  |
| "I learned something I didn't know" (NPS proxy)     | > 50%  |

Without an agent, all of these collapse into either (a) hand-coded
per-org rules that break on the next ECO numbering scheme, or
(b) generic outputs the engineers ignore.

---

## "What if we just used GPT once at the end?"

Common pattern: dump everything into a single Sonnet call once a day,
ask for "what's important?" That's the cheapest LLM approach. We
don't do it because:

1. **Context window cost.** 200 users × 100 messages/day = 20k
   messages. Doesn't fit, won't fit cheaply.
2. **Personalisation impossible.** Same prompt, same output. We
   need per-user briefings.
3. **No durable understanding.** Each day the LLM starts from
   scratch. We need decisions + Cards + edges to persist as DB
   rows for search / impact / audit.
4. **No tool use.** Can't link to PRs, can't query Drive folders
   later.

Agent-per-decision-point + structured outputs + RAG = right model.
Single-shot summarisation = toy demo.

---

## What does this look like for the take-home demo

When a reviewer installs EverCurrent into their Slack workspace:

1. They install. We backfill 30 days. (workflow, no agent).
2. Router agent processes every message in backfill. Each gets
   tags + entities + maybe a Card. (agent, batched).
3. Linker agent builds edges between cards + docs + threads.
   (agent).
4. Reviewer opens dashboard. Sees Cards. Sees timeline. Sees their
   morning digest (regenerated on demand for the demo).
5. Reviewer asks Chat: *"What decision did Lin push back on last
   week?"* — agent uses search_messages + query_decisions tools,
   answers with citations. (agent).
6. Reviewer clicks Card → sees decision + cited sources + impact +
   linked PRs.

Reviewer thinks: "the agent did the boring work I'd have done by
hand." That's the impact.
