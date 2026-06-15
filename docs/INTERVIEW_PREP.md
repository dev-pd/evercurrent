# EverCurrent — Interview Question Bank

A self-test deck for defending this codebase. Grouped by theme. Most
entries are questions only — answer them out loud, then check against the
code. The hardest ones have a short pointer. Pair this with
`docs/SYSTEM_DESIGN.md` (the flows) and `docs/ARCHITECTURE.md`.

How to use: cover the pointer, answer cold, then open the file named and
verify. If you can't answer in 2-3 sentences, you don't own it yet.

---

## 1. Architecture & layering

1. Walk me through the layers from an HTTP request to the database. What
   is and isn't allowed in each? (routes → services → repositories → DB.)
2. Why are domain models separate from SQLAlchemy models? What's the cost
   of mapping between them, and is it worth it?
3. What's the adapter pattern doing here? Name two adapters and why
   they're swappable. (`LLMProvider`/`AnthropicProvider`,
   `EmbeddingProvider`/`VoyageEmbedder`.)
4. Where does dependency injection happen, and what problem does it solve
   for testing?
5. Why split into `enrichment/`, `scoring/`, `digest/`, `decisions/`,
   `rag/`, `agent/` instead of one service? What's the seam?
6. You have a 400-line file rule and a 50-line function rule. Why? Show a
   place you'd refactor.

## 2. Async pipeline, Celery, the queue

1. Why is *anything* on a background worker instead of in the request?
   What specifically breaks if tagging runs inline in the webhook?
2. Trace a Slack message from webhook to a scored, carded row. Which steps
   are sync, which are queued? (`SYSTEM_DESIGN.md` §3.)
3. What makes every task idempotent? Give the exact mechanism for
   `raw_events`, `messages`, `message_tags`, `scores`, `cards`.
4. Celery Beat runs the digest scan every 60s. Why 60s and not hourly?
   How do you avoid generating the same digest twice in that minute?
5. A burst of 50 Slack messages lands at once. Walk the load path. Where
   does it queue, where's the bottleneck, what degrades? (Sonnet card
   latency; Voyage 3 RPM.)
6. The worker shares one pool for tagging and card-building. What's the
   risk, and how would you fix it? (Card backlog starving tagging →
   separate queues / priorities.)
7. How would you scale the worker horizontally? What has to stay true for
   that to be safe? (Idempotency + no shared local state.)

## 3. Multi-tenancy & RLS (security — they will push here)

1. How do you guarantee one org can't read another's rows? Why isn't a
   `WHERE org_id = …` in application code enough?
2. Explain `SET LOCAL app.current_org_id` and why it's transaction-scoped.
   What bug does transaction-scoping *cause* that you had to handle?
   (Eve's rollback drops the context → re-apply before insert.)
3. What is the `app_rw` role and why can't it bypass RLS? Who runs
   migrations then?
4. "Fail closed" — what does the RLS policy do when the setting is unset,
   and why is that the safe default?
5. How does View-as/impersonation stay inside the org boundary? What stops
   an admin impersonating into another tenant? (`auth/deps.py:174` —
   `target.org_id == org.id` check.)
6. Where does `org_id` first get established for an inbound Slack event vs
   an authenticated HTTP request?
7. JWT auth: what's validated on every request? (RS256 + JWKS + audience +
   the org claim.) What's JIT provisioning and when does it fire?

## 4. Ingestion — Slack webhook, dedup, backfill

1. How is a Slack webhook authenticated? What stops a replay? (HMAC +
   5-min timestamp window.)
2. Slack re-delivers an event you already processed. Trace what happens.
   Where exactly does it stop?
3. What's the difference between `raw_events` and `messages`? Why keep
   both instead of just the normalized table?
4. A workspace connects with 6 months of history. The webhook only sees
   new messages — how do you get the backbook in? (Backfill via
   `conversations.history`.)
5. There was a bug where backfill returned zero messages. What was it?
   (Slack `oldest` cursor must be an integer epoch string, not a float.)
   How would you have caught it faster?
6. How are Slack threads modeled? (`thread_root_id` linked by joining the
   parent's `external_id`.)

## 5. Personalization — the scoring engine (the core IP)

1. Why is ranking deterministic code and not the LLM? Give three reasons.
   (Explainability, testability, safety/no-smuggling.)
2. List the six scoring factors and their weights. Why does
   `topic_weight` get only 0.10? (`scoring/weights.py`.)
3. The same message scores high for one member and ~0 for another.
   Mechanically, why? Walk one factor end to end.
4. What does the `reasons` JSONB on `scores` buy you? (Per-item "why this
   matters to you" — explainability.)
5. How does feedback (👍/👎) change future digests? Trace the path from
   click to a re-ordered digest. (`cards.py` bumps
   `topic_weights[topic]` → scorer → ranking.)
6. Is there a risk of a feedback loop runaway (weights drifting to ±∞)?
   How is it bounded? (`clamp(topic_weight, -1, 1)`.)
7. How would you A/B test a weight change? What metric proves it helped?

## 6. Digest generation (LLM)

1. What does the LLM actually decide vs what's decided before it? (Wording
   + grouping vs ranking.)
2. What's the hallucination guard on the digest? (`_filter_cited_ids` —
   drop invented citations.) Why is "the model can only cite what we fed
   it" the right framing?
3. The LLM call fails at digest time. What does the user see? (Deterministic
   fallback: top-8/next-8/next-8.) Why never an empty digest?
4. Why is the digest generated once a day (or on demand) instead of live
   per message? Cost and product-semantics answer.
5. How is the digest idempotent? (Upsert on `(project_member_id,
   day_index)`.)
6. Walk the prompt: what context goes in? (Member profile, phase +
   phase_concerns, top scored items, open cards, prior digests.) That last
   one — why feed prior digests? (Novelty/continuity.)

## 7. Realtime — SSE & the Next.js model

1. Why SSE and not polling? Why not WebSocket? (Server-push of unsolicited
   events; one-directional.)
2. What unsolicited events justify a standing connection? (Teammate's
   message, 8am digest, Eve insight — no request to ride back on.)
3. You click Regenerate; the POST returns 202 with no digest. How does the
   new digest reach the screen? (SSE `digest_ready` → `router.refresh()`
   → server re-fetch.)
4. Why is there "no `/api/` call" in the browser after regenerate? (Digest
   is fetched in a server component; the call originates from the Next
   server, not the browser.)
5. **The SSE triple-bug story.** Three independent breaks kept realtime
   dead. Name them. (Wrong channel `org_id` vs `project_id`; redis
   socket-timeout crashing the stream; named `event: update` so
   `onmessage` never fired.) How did you isolate each?
6. The digest is server-rendered with no client query. So what does
   `invalidateQueries(["digest"])` do? (Nothing — that's why you need
   `router.refresh()`.) What's the lesson about server vs client state?

## 8. AI engineering (they'll dig hardest here)

1. **Model tiering** — which model does what and why? (Haiku for
   high-volume tagging; Sonnet for digest/cards/Eve.) What's the cost vs
   quality trade?
2. Where do prompts live and why not inline in Python? (`<module>/prompts/`
   — versionable, eval-able, no redeploy to tweak.)
3. **Context engineering for Eve** — describe all three layers. (Static
   system prompt; dynamic per-run = novelty injection + just-in-time
   retrieval via tools; size discipline = truncation/turn caps.) Which is
   the *main* mechanism? (Agentic retrieval, not a big prompt.)
4. Why retrieval-via-tools instead of stuffing the corpus into the prompt?
   (Relevance, token cost, the model pulls only what it needs.)
5. **Grounding gate** — what failure does it stop, and how does it work?
   (Fabricated evidence; keep only cited snippets whose tokens overlap
   evidence Eve actually retrieved.) Why token-overlap and not exact
   match? (Model paraphrases.)
6. **Confidence gate** — the model self-rates confidence. Isn't that
   gameable / unreliable? Defend it. (Cheap filter, combined with
   grounding + trajectory; not sole gate.)
7. **Trajectory check** — what does "rejected an insight emitted without
   searching" protect against? (Emitting from priors / hallucination with
   no evidence.)
8. **Dedup** — two layers. Prompt-level ("already flagged") and embedding
   cosine ≥ 0.82. Why both? Why 0.82 — how would you tune it? (Labeled
   near-dup vs distinct pairs → precision/recall.)
9. **Evals** — what do you eval and how? (Router accuracy; scoring rank
   correlation; RAG precision@5/MRR; digest LLM-judge; Eve
   recall/precision + grounding judge.) Why is the judge run at
   temperature 0.0?
10. Why is the eval harness **not** a CI gate? (LLM nondeterminism +
    cost + flakiness; it's a baseline-warning tool, run on demand.)
11. **Eve recall vs precision** — define each for a proactive agent. Which
    is scarier to get wrong and why? (Precision — a confident wrong
    insight kills trust.) How does the eval measure precision? (Clean
    corpus → must abstain.)
12. How do you eval an agent that needs a database? (Fake MCP client
    serving a fixed corpus — no DB.) What does that *not* test?
13. LLM-as-judge: what are its failure modes and how do you keep it
    honest? (Position bias, leniency; strict rubric, temp 0, fixed JSON
    output, human spot-checks.)
14. If you had one week to make Eve production-trustworthy, what's the
    ordered list? (Grounding gate → eval set → human-in-loop →
    confidence calibration → cost budget.)

## 9. Frontend

1. Server components by default — what can't they do, and when do you add
   `"use client"`?
2. Where's server state vs client state? (TanStack Query vs Zustand.)
   Name the Zustand stores and why each exists. (impersonation, regen.)
3. Zod at every boundary — show one boundary and what breaks without it.
4. How does View-as work end to end? (Cookie → `X-Impersonate-User`
   header → `auth/deps` resolves the viewed member.)
5. Why are some events (digest_ready) doing `router.refresh()` and others
   (card_created) debounced? (Frequency — avoid refresh storms.)

## 10. Trade-offs & "what would you change"

1. Single-project-per-org today. What breaks at multi-project and what's
   the migration? (Channel→project mapping + `project_members`.)
2. Voyage free tier is 3 RPM. Where does that bite and what's plan B?
3. Backfill is full-window, no cursor. What's the cost and the fix?
4. The digest fallback is heuristic. When is that *good enough* and when
   would it embarrass you?
5. What's the weakest part of the whole system in your own words? (Pick
   one and own it — Eve precision at scale, or worker scaling, or the
   eval not gating CI.)
6. Where's the biggest security risk if you got one thing wrong? (RLS
   context leaking across the pool — why `SET LOCAL` prevents it.)

## 11. Debugging war-stories (great for "tell me about a hard bug")

Have a crisp 4-part story for each: symptom → hypotheses → isolation →
fix → what you'd do to prevent it.

1. **Realtime never updated.** Symptom: Regenerate stuck "Regenerating…",
   nothing refreshed. Three stacked root causes (channel, timeout-crash,
   named-event). How you peeled them one at a time.
2. **Backfill returned 0 messages.** Float vs integer epoch cursor.
3. **Eve inserted RLS violation.** Rollback dropped `SET LOCAL` context.
4. **Stale prod container.** FE fixes "didn't work" because the running
   container was a baked `next start` build, not HMR.
5. **502s after every rebuild.** nginx cached the old upstream IP; fixed
   with Docker's embedded DNS resolver + variable `proxy_pass`.

## 12. Rapid-fire (one-liners — know cold)

- pgvector dimension and why? (512, `voyage-3-lite`.)
- HNSW vs IVFFlat — which and why?
- Why `timestamptz` not `timestamp`?
- What's `ON DELETE` policy discipline and why required?
- Conventional Commits — why one per subphase?
- Why no `Co-Authored-By`? (Repo policy.)
- What's the cosine dedup threshold and where's it configured now?
  (`eve_dedup_threshold`, config.)
- Haiku vs Sonnet model ids?
- What does `request_id` propagation give you operationally?
- Pydantic `strict=True` everywhere — why?

---

## Closing framing (have this ready)

"This is an **AI-native, multi-tenant** system where the **deterministic
core does the ranking and the LLM does the language**. Everything
expensive or unpredictable is pushed to an **idempotent async queue**, the
**database enforces tenant isolation** (not app code), and the **AI
surfaces are guarded** — hallucination filters on the digest, a grounding
+ confidence + trajectory gate on the agent, and an **offline eval
harness** that scores quality without pretending LLM output is
deterministic. Where it's synthetic (timeline, demand), it's labeled
synthetic. The weakest spot is X and here's how I'd harden it."
