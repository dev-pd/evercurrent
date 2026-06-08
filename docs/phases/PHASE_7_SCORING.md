# Phase 7 — Scoring

## Goal

A pure-Python, deterministic relevance engine. Given a message and a
project member, return a single number in `[0, 1]` that says "how much
should this person care about this message." No LLM, no network call,
sub-millisecond. The score is computed once per `(member, message)`
pair, written to the `scores` table, and read repeatedly by the digest
agent and the dashboard. Heavy TDD this phase — this is exactly the
kind of code unit tests were invented for.

## Why this phase, this order

The router agent (phase 5) tags every message with topic, urgency,
entities, and `affected_roles`. The cards builder (phase 6) materialises
the important ones. But the digest agent (phase 8) is per-user — it
needs to rank items for *this* engineer in *this* role with *these*
owned subsystems. That ranking is not an LLM problem. It is a weighted
sum of signals we already have in the database.

Doing scoring as pure Python before we build the digest agent buys
three things. First, the digest prompt becomes radically smaller —
"here are the top 20 items for Sarah" instead of "here are 400 messages,
figure out what matters." Second, cost stays sane: 200 users × 1 daily
digest call instead of 200 users × 400 LLM judge calls. Third, the
score is auditable — we can show the user "this is in your top 5
because role_match=1.0, urgency_boost=0.6, subsystem overlap on
[chassis]."

The order inside the phase: schemas first (so the engine has typed
inputs/outputs), weights config second (one knob to tune), engine
third (TDD'd against the schemas), repository fourth (write the row),
celery task last (wire it after the router).

## Pre-requisites

- Phase 5 done (`message_tags` rows exist with `topic`, `urgency`,
  `entities`, `affected_roles`)
- Phase 6 done (`cards` and `card_sources` populated, but scoring does
  not depend on them yet — it scores raw messages)
- `project_members` rows exist with `role`, `owned_subsystems`, and
  `topic_weights` JSONB
- `projects.phase_concerns` populated by phase 2 / seed data

## Files touched

### New
- `apps/api/src/evercurrent/scoring/__init__.py`
- `apps/api/src/evercurrent/scoring/schemas.py` — `ScoreInput`,
  `ScoreBreakdown`, `ScoreOutput` Pydantic models
- `apps/api/src/evercurrent/scoring/weights.py` — single `WEIGHTS` dict
- `apps/api/src/evercurrent/scoring/engine.py` — `score(input) -> output`
- `apps/api/src/evercurrent/scoring/repository.py` —
  `upsert_score(session, project_member_id, message_id, output)`
- `apps/api/src/evercurrent/scoring/service.py` —
  `score_message_for_all_members(message_id)` orchestrator
- `apps/api/tests/unit/scoring/test_engine.py` — the heavy TDD file
- `apps/api/tests/unit/scoring/test_weights.py` — invariant tests
- `apps/api/tests/unit/scoring/conftest.py` — fixtures for
  `ScoreInput` with sane defaults

### Modified
- `apps/api/src/evercurrent/jobs/celery_tasks.py` — add
  `score_message_for_members(message_id)` task; chain after
  `route_message`
- `apps/api/src/evercurrent/db/models.py` — ensure `Score` model exists
  (table from phase 0 baseline)
- `apps/api/src/evercurrent/db/repositories/__init__.py` — export
  scoring repository

### Deleted
- nothing

## Tasks

1. **Define schemas.** `scoring/schemas.py`:
   ```python
   class ScoreInput(BaseModel):
       model_config = ConfigDict(strict=True)
       # message-side
       message_id: UUID
       author_role: str
       topic: str | None
       urgency: Literal["critical", "high", "normal", "low"] | None
       entities: list[str] = []
       affected_roles: list[str] = []
       # member-side
       project_member_id: UUID
       member_role: str
       owned_subsystems: list[str] = []
       topic_weights: dict[str, float] = {}
       # project-side
       current_phase_concerns: list[str] = []

   class ScoreBreakdown(BaseModel):
       role_match: float
       subsystem_match: float
       urgency_boost: float
       phase_concern_match: float
       topic_weight: float
       cross_functional: float

   class ScoreOutput(BaseModel):
       score: float           # final clamped value
       breakdown: ScoreBreakdown
   ```
2. **Define weights.** `scoring/weights.py`:
   ```python
   WEIGHTS: dict[str, float] = {
       "role_match":          0.25,
       "subsystem_match":     0.25,
       "urgency_boost":       0.20,
       "phase_concern_match": 0.15,
       "topic_weight":        0.10,
       "cross_functional":    0.05,
   }
   # must sum to 1.0 — asserted in tests
   ```
3. **Write the engine.** `scoring/engine.py`:
   - `_role_match(inp) -> float`: `1.0` if `inp.member_role in inp.affected_roles` else `0.0`
   - `_subsystem_match(inp) -> float`: count of overlap between
     `inp.entities` and `inp.owned_subsystems`, clamped at `1.0`
   - `_urgency_boost(inp) -> float`: map
     `{critical: 1.0, high: 0.6, normal: 0.3, low: 0.0}`, default `0.0`
   - `_phase_concern_match(inp) -> float`: `0.7` if `inp.topic` in
     `inp.current_phase_concerns` else `0.0`
   - `_topic_weight(inp) -> float`:
     `inp.topic_weights.get(inp.topic, 0.0)` clamped to `[-1.0, 1.0]`
   - `_cross_functional(inp) -> float`: `0.4` if
     `inp.author_role != inp.member_role` AND subsystem overlap > 0,
     else `0.0`
   - `score(inp) -> ScoreOutput`: linear combination, then
     `max(0.0, min(1.0, raw))`. Build the `ScoreBreakdown` for audit.
4. **Repository write.** `scoring/repository.py`:
   `upsert_score(session, project_member_id, message_id, output)` runs
   `INSERT ... ON CONFLICT (project_member_id, message_id) DO UPDATE`.
   `reasons` JSONB stores the `breakdown.model_dump()`.
5. **Orchestrator service.** `scoring/service.py`:
   `score_message_for_all_members(session, message_id)`:
   - Load message + tags via repository.
   - Load `project_members` for the message's project.
   - For each member, build a `ScoreInput`, call `engine.score`,
     upsert. No I/O concurrency needed here — the inner loop is pure
     Python and the writes batch in one transaction.
6. **Celery task.** In `jobs/celery_tasks.py`:
   ```python
   @app.task(name="score_message_for_members")
   def score_message_for_members(message_id: str) -> None:
       asyncio.run(_score_message_for_members(UUID(message_id)))
   ```
   Chain after `route_message` so the router writes tags, then scoring
   fans out.
7. **TDD — write the tests first.** Before the engine body, write
   every test in §"Test plan" below. Each should fail. Then make
   them pass in order.
8. **Run `make lint`, then `make test-unit`.** Should be all green.
9. **Commit.** `feat(phase-7): pure-python scoring engine + per-member fanout`.

## Test plan

Heavy TDD this phase. Every test below sits in
`apps/api/tests/unit/scoring/test_engine.py` and runs in
under 50 ms total (no DB, no network).

Deterministic engine tests (write all of these BEFORE the engine):

- `test_score_zero_when_no_signals` — empty input → all components
  zero → score is `0.0`.
- `test_role_match_adds_role_weight` — affected_roles contains
  member_role → `breakdown.role_match == 1.0`; score increases by
  exactly `WEIGHTS["role_match"]`.
- `test_subsystem_overlap_one_entity` — one overlap → `0.something`
  contribution.
- `test_subsystem_overlap_clamps_at_one` — five entities all in
  owned_subsystems → `breakdown.subsystem_match == 1.0` (not 5.0).
- `test_urgency_critical_dominates` — only critical urgency set →
  `breakdown.urgency_boost == 1.0`.
- `test_urgency_low_contributes_zero` — `low` urgency → boost is `0.0`.
- `test_urgency_unknown_defaults_to_zero` — `None` or unmapped string
  → `0.0`.
- `test_negative_topic_weight_suppresses_score` — `topic_weights =
  {"firmware": -1.0}`, topic `firmware`, all other signals at 1.0 →
  final score is strictly less than the "no topic_weight" baseline.
- `test_positive_topic_weight_boosts_score` — symmetric to above with
  `+1.0`.
- `test_score_clamps_between_zero_and_one` — pump every component to
  its maximum → final score is exactly `1.0`, not `1.7`. Then pump
  topic_weight to `-1.0` with zero everywhere else → final score is
  `0.0`, not negative.
- `test_cross_functional_only_when_subsystem_overlap` — different
  roles but no subsystem overlap → `cross_functional == 0.0`.
- `test_cross_functional_active_with_overlap` — different roles AND
  one overlap → `cross_functional == 0.4`.
- `test_cross_functional_zero_when_same_role` — same role, even with
  overlap → `cross_functional == 0.0`.
- `test_phase_concern_match_uses_current_phase` — topic
  `thermal_margin` is in `current_phase_concerns` → match contributes
  `0.7 * WEIGHTS["phase_concern_match"]`.
- `test_phase_concern_no_match` — topic absent from phase concerns →
  contribution `0.0`.
- `test_score_is_deterministic_for_same_inputs` — call `score` twice
  with identical input; results compare exactly equal (regression
  guard against any future randomness creeping in).
- `test_breakdown_components_match_individual_helpers` — the
  `ScoreBreakdown` returned by `score()` equals what you'd get
  calling each helper directly. Locks the contract for the dashboard
  "why is this in my top 5" surface.

Weights invariant tests (`test_weights.py`):

- `test_weights_sum_to_one_invariant` —
  `sum(WEIGHTS.values()) == pytest.approx(1.0)`.
- `test_weights_are_all_non_negative` — every value `>= 0.0`.
- `test_weights_keys_match_breakdown_fields` — the WEIGHTS keys are
  exactly the field names on `ScoreBreakdown`. Catches typos that
  would silently drop a component from the sum.

Service-level test (one only, to prove fanout):

- `test_score_message_for_all_members_writes_one_row_per_member` —
  integration-ish with the in-memory session fixture; given a project
  with 3 members and one tagged message, calling the service writes
  exactly 3 `scores` rows. Already covered by phase 1 fixtures.

## Definition of done

- [ ] `scoring/engine.py` returns a `ScoreOutput` in `[0, 1]` for any
      valid `ScoreInput`
- [ ] All tests in §"Test plan" pass
- [ ] `WEIGHTS` invariant holds (sums to 1.0, all non-negative, keys
      match breakdown fields)
- [ ] `score_message_for_members` Celery task is registered and chained
      after `route_message`
- [ ] After ingesting a Slack message and running the worker, one
      `scores` row exists per project member of that message's project
- [ ] Each `scores.reasons` JSONB contains the full breakdown
- [ ] `make lint`, `make test-unit` clean
- [ ] One commit on `feat/phase-7-scoring` branch, merged to `main`

## Common pitfalls

- **Floats compared with `==`.** Use `pytest.approx` for any sum of
  components. The `WEIGHTS` invariant test will lie to you with raw
  `==` because `0.25 + 0.25 + 0.20 + 0.15 + 0.10 + 0.05` is not
  exactly `1.0` in IEEE 754.
- **Clamping in the wrong place.** Clamp the final score, not each
  component pre-multiplication. Otherwise the urgency_boost saturates
  before its weight applies and the dial does nothing.
- **Forgetting to clamp `topic_weight`.** It's user-driven feedback;
  if a bug lets it grow to `+5.0`, one negative thumbs-down doesn't
  un-stick the score. Clamp on read.
- **Storing the breakdown as Python `repr()` instead of JSON.** Use
  `model_dump(mode="json")` so the dashboard can render it without
  custom parsing.
- **Putting LLM calls in here "for slightly better topic matching."**
  No. The whole point of this phase is determinism + speed. If
  fuzziness matters, fix it in tagging (phase 5).
- **Fanning out scoring across processes.** One project has at most a
  few hundred members. The whole fanout is pure Python and one bulk
  insert. Don't spawn 200 Celery sub-tasks per message — the queue
  overhead dwarfs the work.
- **Re-scoring on every read.** `scores` is precomputed. The dashboard
  query is `SELECT * FROM scores WHERE project_member_id = ? ORDER BY
  score DESC LIMIT 20`. If you find yourself re-computing on read,
  back up — that's why the table exists.

## Recap — what you'll be able to explain after this phase

- "Why pure Python, not LLM?" → Cost (200 users × 1000 messages/day
  of LLM judging is hundreds of dollars), determinism (the same
  inputs always produce the same output, so users can trust their
  ranking), and latency (sub-millisecond, so the digest agent can
  fan out 200 users in a few seconds total). LLM is reserved for
  *understanding* (tagging) and *writing* (digest). Ranking is math.
- "Why precompute the scores table instead of computing on read?" →
  Reads are bursty. At 8am local time, every dashboard load and
  every digest agent run queries the top-N for one member. Doing
  the math on read means the LLM tagging hits the same rows
  hundreds of times. Precompute once per `(member, message)`, store,
  read cheaply.
- "Why store the breakdown?" → Debuggability and user transparency.
  When Sarah asks "why is this in my top 5?" we can show her
  `role_match=1.0, subsystem overlap on [chassis], urgency=high`.
  Same data also drives feedback loop tuning: if items with high
  `topic_weight` consistently get thumbs-down, we know the weight
  for that signal is too high.
- "How do you tune the weights?" → Weights live in one dict in
  `scoring/weights.py`. Eval harness (phase 12) replays seeded
  scenarios with different weight vectors and measures
  precision@5 against hand-labeled "should be in top 5" sets.
- "How do you guard against silent regressions?" → The deterministic
  test `test_score_is_deterministic_for_same_inputs` plus the
  `test_breakdown_components_match_individual_helpers` lock the
  contract. The weights-keys-match-breakdown invariant catches the
  classic refactor bug of adding a field but forgetting to weight it.

## Talking points (for the grill)

1. **"Scoring is pure Python because it's math."** Cost,
   determinism, latency — all three argue against LLM judging here.
2. **"The breakdown is part of the API."** Every score is auditable.
   The user can see why an item is in their top 5; the eval harness
   can isolate which signal is mis-calibrated.
3. **"Precomputed scores table, denormalised on purpose."** One row
   per `(member, message)`. Reads are O(top-N) index scans. Writes
   happen once when the router fires.
4. **"Weights live in one config dict."** Tuning is changing six
   numbers and re-running evals. No code change to ship a weight
   tweak.
5. **"TDD because the engine is the load-bearing function in
   personalisation."** Every signal has at least one test for "on"
   and one for "off." The clamp tests guard the contract.
6. **"Cross-functional is the most interesting signal."** It's the
   one that catches "the firmware team's PR affects the chassis
   engineer because of subsystem overlap." Without it, scoring
   degenerates into single-role bubbles.
