# Phase 12 — Polish + evals + demo

## Goal

Take a feature-complete codebase to a demo-ready submission. Build the
eval harness, write the baseline numbers, rewrite the README, author
the demo script and code tour, and finalise the decisions doc. By the
end of this phase a reviewer can clone the repo, read four short docs,
run two make commands, and watch a 10-minute live demo without
surprises.

This phase ships no new product features. It ships *understanding* —
the kind that turns "interesting prototype" into "this person knows
how to deliver."

## Why this phase, this order

Every prior phase added behaviour. This one adds the surface that
makes behaviour legible to someone who has 30 minutes to evaluate
your work. The eval harness gives the AI-quality dimension a number
instead of a vibe. The demo script is the rails the live walkthrough
runs on. The README + code tour + decisions doc are the artefacts
that survive the interview and travel with the code.

Last by design. Earlier the codebase wasn't stable enough to lock in
baseline eval numbers; rerunning every time a prompt changes is a
waste. With Phases 0-11 frozen the numbers mean something.

Order inside the phase: evals first (the numbers feed the talking
points), demo script second (the script forces a final pass through
the working product), README + tour + decisions third (writing up
what is already true), recording optional last.

## Pre-requisites

- Phases 0-11 complete, lint clean, definition-of-done checklists
  green
- A real Slack workspace with 30 days of demo messages backfilled
- A Drive folder with the 5 sample PDFs ingested (or the mock-drive
  path proven to work end-to-end)
- A demo user account with subscriptions configured

## Files touched

### New

- `apps/api/tests/evals/__init__.py`
- `apps/api/tests/evals/eval_router.py` — 50-message tag accuracy
- `apps/api/tests/evals/eval_rag.py` — 30-pair precision@5 + MRR
- `apps/api/tests/evals/eval_digest.py` — 5-scenario LLM-as-judge
- `apps/api/tests/evals/eval_scoring.py` — 20-scenario ranking
- `apps/api/tests/evals/data/router_labels.json`
- `apps/api/tests/evals/data/rag_pairs.json`
- `apps/api/tests/evals/data/digest_scenarios.json`
- `apps/api/tests/evals/data/scoring_scenarios.json`
- `apps/api/tests/evals/judge_prompts/digest_rubric.txt`
- `docs/EVAL_BASELINE.md` — current numbers + method
- `docs/CODE_TOUR.md` — file-by-file walkthrough in reading order

### Modified

- `Makefile` — add `eval`, `eval-router`, `eval-rag`, `eval-digest`,
  `eval-scoring` targets
- `docs/DEMO_SCRIPT.md` — rewrite as a 10-minute live walkthrough
- `docs/DECISIONS.md` — final pass, every architectural choice
  answered with rationale
- `README.md` — one-paragraph what-is-this + quick start + doc index

### Deleted

- nothing

## Tasks

1. **Eval data sets.** Hand-label the four datasets. Don't generate
   them with another LLM — the eval signal becomes circular.
   - `router_labels.json`: 50 entries. Each row is
     `{message_text, channel, expected: {topic, urgency, entities,
     affected_roles}}`. Pull 50 messages from the demo workspace
     spanning the 6 roles + 5 topic areas.
   - `rag_pairs.json`: 30 entries. Each row is `{question,
     expected_chunk_ids: list[uuid]}`. Questions written by hand
     against the 5 ingested PDFs; expected chunks identified by
     reading.
   - `digest_scenarios.json`: 5 entries. Each is
     `{seed_message_ids: list[uuid], member_id, expected_phase}`.
     The eval generates a digest from this seed and the judge scores
     it.
   - `scoring_scenarios.json`: 20 entries. Each is
     `{message_text, message_tags, member_profile, expected_relative_rank}`.
     Tests assert the engine ranks scenarios consistently.
2. **Router eval (`eval_router.py`).** For each labelled message:
   - Run the Router agent (Phase 5) end-to-end.
   - Compare predicted tags to expected per field.
   - Topic, urgency: exact match. Entities, affected_roles: set
     overlap precision + recall.
   - Aggregate accuracy per field.
   - Target: > 90% accuracy on topic + urgency, > 0.85 F1 on
     entities + roles.
3. **RAG eval (`eval_rag.py`).** For each question:
   - Call MCP `search_documents(question, project_id, k=5)`.
   - Compute precision@5: fraction of returned chunks that are in
     the expected set.
   - Compute MRR: 1 / rank of the first expected chunk in the
     result.
   - Average across the 30 questions.
   - Target: precision@5 > 0.7, MRR > 0.6.
4. **Digest eval (`eval_digest.py`).** For each scenario:
   - Generate a digest via the Digest agent (Phase 8) seeded from
     the scenario.
   - Run a separate Sonnet call as the judge, prompted with
     `judge_prompts/digest_rubric.txt`: score 1-5 on relevance,
     citation correctness, voice, length.
   - Save per-scenario scores. Aggregate the mean.
   - Target: > 4/5 on all four axes averaged.
5. **Scoring eval (`eval_scoring.py`).** Pure Python, no LLM:
   - For each scenario, run the scoring engine (Phase 7) on the
     synthetic message + member profile.
   - Assert the relative rank matches `expected_relative_rank`.
     ("This message should rank above scenario X for this profile.")
   - Pass/fail per scenario; report count.
6. **Makefile targets.** `make eval` runs all four. Individual
   targets for each. Each prints a summary table; the aggregate
   target also writes `tests/evals/results/{date}.json` for
   regression tracking.
7. **`EVAL_BASELINE.md`.** Document current numbers. Method
   description: dataset size, what's measured, judge prompt link,
   honest caveats. Note: numbers are reference, not gates. CI does
   not run evals.
8. **`DEMO_SCRIPT.md`.** Rewrite as a timed 10-minute walkthrough:
   - Section 1 — Architecture (2 min). Open `SYSTEM_DESIGN.md` to
     the §1 diagram. Walk left to right: browser → FastAPI → Postgres
     + Redis → Celery → Anthropic + Voyage. One sentence each on the
     why.
   - Section 2 — Live ingest (2 min). Post a message in
     `#mech-design` in the demo workspace. Switch to the dashboard
     tab. Watch the Card appear within a few seconds. Open it, point
     out the Router agent's tags + the linked thread.
   - Section 3 — Digest (2 min). Click "Regenerate" on the digest.
     Walk through the three priority buckets. Click into one item
     and show the citation chain back to a Slack message.
   - Section 4 — PDF flow (2 min). Drop a PDF in the watched Drive
     folder (or run `mock_drive_ingest.py` against the fixtures).
     Show the new document + the Card it produced.
   - Section 5 — Code tour (2 min). Open the files
     `CODE_TOUR.md` recommends, in order. Talk about the layering and
     where the agent lives.
9. **`CODE_TOUR.md`.** A reader's guide. File-by-file in the order a
   reviewer should open them during a code grill:
   1. `apps/api/src/evercurrent/main.py` — the entry point + lifespan
   2. `apps/api/src/evercurrent/api/routers/webhooks.py` — Slack +
      Drive webhooks, the front door for ingest
   3. `apps/api/src/evercurrent/jobs/celery_tasks.py` — what runs
      where in the background
   4. `apps/api/src/evercurrent/routing/router_agent.py` — the
      Haiku call + Pydantic schemas
   5. `apps/api/src/evercurrent/cards/builder.py` — the deterministic
      Card creation rules
   6. `apps/api/src/evercurrent/scoring/engine.py` — the pure-Python
      relevance score
   7. `apps/api/src/evercurrent/digest/agent.py` — the Sonnet call
   8. `apps/api/src/evercurrent/mcp/server.py` — the tool layer
   9. `apps/api/src/evercurrent/notify/slack_deliver.py` — DM
      delivery
   10. `apps/web/app/dashboard/page.tsx` — hero screen
   11. `apps/web/hooks/use-digest.ts` — SSE + TanStack Query pattern
10. **`DECISIONS.md` final pass.** Every architectural choice gets
    one paragraph: what, why, what we considered, what we rejected,
    when we'd change our mind. Required entries:
    - Celery + Beat vs Temporal
    - FastMCP vs bespoke tool registry
    - Auth0 vs Clerk vs hand-rolled
    - Postgres + pgvector vs separate vector DB
    - voyage-3-lite vs OpenAI ada-002 vs e5-large
    - Push webhooks vs polling for Drive + Slack
    - Postgres RLS for tenancy vs app-layer filtering
    - Router + Digest split vs one mega-agent
    - Pre-computed digest vs on-demand
    - Server components by default vs all-client React
    - TanStack Query vs SWR vs raw fetch + useEffect
    - PyMuPDF vs pdfplumber vs Unstructured
    - 800-char chunks vs 400 vs 1500
11. **`README.md` rewrite.** One paragraph "what is this". A
    `make up && make migrate` quick start with URLs to visit. A
    documentation index pointing to PRD, SYSTEM_DESIGN, DECISIONS,
    AGENT_VS_WORKFLOW, and `docs/phases/README.md`. Nothing else.
    Resist the urge to repeat content from elsewhere.
12. **Master DoD checklist.** Go phase by phase, tick every
    definition-of-done box. Anything red gets fixed or explicitly
    noted as "out of scope for take-home, on roadmap."
13. **Integration smoke pass.** End-to-end test the full demo: fresh
    `make up`, install the demo org, run backfill, open dashboard,
    drop a Slack message, drop a PDF, regenerate digest, receive DM.
    Time each step; fail if any exceeds the targets we've claimed
    (5s ingest, 30s digest).
14. **Optional recording.** Loom or QuickTime; 10 minutes; follows
    `DEMO_SCRIPT.md` exactly. Not required if the live demo is the
    submission format.
15. **Commit.** `chore(phase-12): evals + demo script + README + decisions`.

## Test plan

Phase 12 is not a TDD phase. Tests already exist for every prior
phase; the eval harness *is* the deliverable, not the thing being
tested. Verification consists of:

- `make eval` runs all four evals to completion.
- Numbers in `EVAL_BASELINE.md` match what `make eval` prints.
- The 10-minute live walkthrough completes without surprises.
- A reader following `README.md` quick start reaches a running
  dashboard in < 10 minutes.
- A reader following `CODE_TOUR.md` can describe the layering in
  their own words.

## Definition of done

- [ ] Four eval scripts run and produce numbers
- [ ] `EVAL_BASELINE.md` published with current numbers + method
- [ ] Router eval ≥ 90% on topic + urgency
- [ ] RAG eval precision@5 ≥ 0.7
- [ ] Digest eval ≥ 4/5 on all four rubric axes
- [ ] Scoring eval all 20 scenarios pass
- [ ] `DEMO_SCRIPT.md` is a timed 10-minute walkthrough
- [ ] `CODE_TOUR.md` ordered file walk-through is written
- [ ] `DECISIONS.md` has an entry for every architectural choice listed
- [ ] `README.md` rewritten, < 100 lines, links to deeper docs
- [ ] Every phase's definition of done is green
- [ ] Integration smoke run completes on a fresh `make up`
- [ ] Optional recording produced or live walkthrough rehearsed
- [ ] One commit on `chore/phase-12-polish` branch, merged to `main`

## Common pitfalls

- **LLM-generated eval labels.** Tempting because it's fast.
  Avoid — the eval becomes "does the LLM agree with itself?". Hand
  label the 50 + 30 + 5 + 20. It's a half-day of work and the signal
  is real.
- **Running evals in CI.** The cost adds up (Sonnet judge × 5
  scenarios per PR is real money), and LLM nondeterminism makes the
  pass/fail flap. Keep evals out of CI. They're a periodic
  reference number, not a gate.
- **Demo script drift.** Writing the script before you've finalised
  the FE polish leads to "click here → wait, that button moved."
  Write it last, after the smoke pass.
- **README that recaps the PRD.** The PRD is one click away. Don't
  duplicate. README's job is "what + get running"; everything else
  links out.
- **DECISIONS doc that lists tools but skips the why.** "We use
  Celery." OK — *why?* "Because we picked it." Not good enough.
  Every entry needs the trade-off and the rejection.
- **Code tour that opens 30 files.** Reviewer attention span is 8
  files. Pick the 8-12 that matter, ordered.
- **Forgetting the master DoD checklist.** The thing that catches
  the one box you skipped in Phase 7. Do it once at the end.
- **Polishing the recording instead of the live demo.** A bad live
  demo with a great recording is worse than a great live demo with no
  recording. Practice the live one.

## Recap — what you'll be able to explain after this phase

- "How do you know the AI quality is any good?"
  → Four evals. Router accuracy on hand-labelled messages, RAG
    precision@5 + MRR on hand-labelled question/source pairs, digest
    LLM-as-judge rubric, scoring engine scenario ranking. Numbers are
    in `EVAL_BASELINE.md`. They're not in CI because Sonnet judge
    costs money and the signal is noisy on a per-commit basis;
    they're a release-gate I run before a tag.
- "Why hand-label 50 messages instead of generating thousands?"
  → Quality > quantity for the signal we need. 50 carefully picked
    cases that cover the topic + urgency + role space gives a
    reliable accuracy estimate. LLM-generated 5,000 messages would
    inflate the number while measuring "does the model agree with
    another model" — circular. Eval cost is also a real constraint;
    50 messages × 1 Haiku call is ~$0.01 to run.
- "Why LLM-as-judge for the digest?"
  → Digest output is subjective — there is no single correct
    briefing. A rubric-based Sonnet judge on (relevance, citations,
    voice, length) gives a directional signal cheap. We sanity-check
    by hand-reading the 5 scenarios occasionally; the judge has been
    aligned with our intuition so far. We document the limitations
    of judge bias openly.
- "Why are evals not in CI?"
  → Two reasons. Cost: each run is ~$0.50 for the judge calls;
    multiplied across PRs that's a real budget hit. Determinism: LLM
    responses vary, so the same prompt can produce different scores
    across runs, which means a green CI on Monday can flap red on
    Tuesday with no code change. Putting flaky checks in CI trains
    the team to ignore CI. Better to run them deliberately, on a
    schedule + on tag.
- "What does the README owe a reviewer?"
  → Three things in this order: one paragraph that tells them what
    EverCurrent is (not what they'll find in PRD §1 — the elevator
    pitch), the two commands to run it locally (`make up && make
    migrate`), and a documentation index pointing to the deeper
    docs. Anything beyond that is duplication.

## Talking points (for the grill)

1. **"Evals are a number, not a vibe."** Four scripts, four
   reference numbers, hand-labelled ground truth.
2. **"Evals are not a CI gate."** Cost + nondeterminism. They're a
   release tool, not a per-commit tool. Documented as such.
3. **"Demo script is timed."** 10 minutes, 5 sections, 2 minutes
   each. I rehearsed it; you'll see no fumbling.
4. **"DECISIONS.md is the antidote to 'why didn't you use X?'"**
   Every choice has the trade-off written down. I'll show you the
   one you're about to ask about.
5. **"README is short on purpose."** One paragraph + quick start +
   doc index. Reviewer reads it in 60 seconds and knows where to
   look next.
6. **"Code tour is the order I'd open the files."** Eight files,
   read top-to-bottom. By file 8 you understand the whole pipeline.
7. **"Every phase's DoD is green or explicitly deferred."** Master
   checklist makes the deferrals visible.
8. **"Live demo first, recording optional."** I'd rather show you
   the thing than play a video of the thing.
