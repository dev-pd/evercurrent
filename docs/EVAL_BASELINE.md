# EverCurrent — Eval Baseline

## What this document is

A reference card for the four offline evals that measure the AI quality
of the system. The contract:

- The evals live under `apps/api/tests/evals/`.
- `make eval` runs all four; `make eval-router`, `make eval-scoring`,
  `make eval-rag`, `make eval-digest` run them individually.
- Results land in `apps/api/tests/evals/reports/<isoformat>_<name>.json`.
- Baselines are **reference numbers, not gates**. A baseline miss logs
  to stderr but does not fail the test. CI does not run `make eval`
  for reasons covered in `docs/DECISIONS.md` ADR-013.
- Ground truth is hand-labelled. Generating ground truth with another
  LLM produces a circular signal — see Phase 12 spec, "Common pitfalls."

## The four evals

| Eval     | What it measures                              | Dataset                  | Cost per run |
|----------|-----------------------------------------------|--------------------------|--------------|
| router   | Haiku tag accuracy per field                  | 50 hand-labelled msgs    | ~$0.02       |
| scoring  | Pure-Python ranking against expectations      | 20 scenarios             | $0           |
| rag      | pgvector retrieval quality                    | 30 Q + 8 corpus docs     | ~$0.01       |
| digest   | Sonnet writer judged by Sonnet on a rubric    | 5 personas               | ~$0.50       |

Total for a full `make eval` run: roughly $0.55 in API spend.

## Metric table

| Eval     | Metric                          | Baseline target | How it's computed                                       |
|----------|---------------------------------|-----------------|---------------------------------------------------------|
| router   | topic accuracy                  | >= 0.85         | substring containment vs expected; 50 rows              |
| router   | urgency accuracy                | >= 0.90         | exact-match on the 4-value Literal                      |
| router   | entities jaccard                | >= 0.60         | case-insensitive set jaccard, averaged                  |
| router   | affected_roles jaccard          | >= 0.70         | case-insensitive set jaccard, averaged                  |
| router   | should_create_card accuracy     | >= 0.85         | exact bool match                                        |
| scoring  | spearman rank correlation       | >= 0.80         | expected vs actual rank of the focus msg in 20 distractors |
| rag      | precision@5                     | >= 0.70         | fraction of top-5 chunks in the expected doc set        |
| rag      | mean reciprocal rank            | >= 0.55         | 1 / rank of first expected doc                          |
| digest   | mean relevance (rubric 0-5)     | >= 4.0          | Sonnet-as-judge on member fit + topic coverage          |
| digest   | mean citation correctness (0-5) | >= 4.0          | judge checks every cited id appears in input set        |
| digest   | mean voice second person (0-5)  | >= 4.0          | judge checks tone, terseness, "you" voice               |
| digest   | mean length budget (0-5)        | >= 4.0          | judge checks 250-400 word target + 3-section structure  |

## How to run

```bash
# All four, with API keys (real LLM calls)
export ANTHROPIC_API_KEY=sk-ant-...
export VOYAGE_API_KEY=pa-...
make eval

# Just the deterministic one (no keys needed)
make eval-scoring

# Just the router (Haiku only, cheap)
make eval-router

# Just the digest (Sonnet writer + Sonnet judge — the expensive one)
make eval-digest

# Just the RAG retrieval (Voyage + testcontainers Postgres)
make eval-rag
```

Without `ANTHROPIC_API_KEY`, the router and digest evals skip with a
clear reason. Without `VOYAGE_API_KEY`, the RAG eval skips. The
scoring eval has zero external dependencies and always runs.

## How to interpret

- A baseline miss is a signal to look. Open the printed per-row table,
  find the lowest-scoring rows, and read the prompt + actual output.
  Most regressions are prompt drift in a single field (`topic` slug
  changes, `affected_roles` vocabulary widens). Fix the prompt or
  re-label the dataset, not the metric.
- A passing baseline is not a quality guarantee. The router can hit
  0.90 urgency accuracy and still be subtly wrong on the long tail.
  Pair the numbers with a human read of `reports/` once a release.
- The digest eval uses LLM-as-judge. Treat the absolute value with
  caution; the *trend* across runs is the signal. A 4.2 today and 3.9
  next week with no code change is noise. A 4.2 dropping to 2.5 is a
  real regression in prompt or context.

## What we DO NOT test

- **String-match assertions on LLM output.** "the digest must contain
  the word 'thermal'" is a brittle test that breaks every time the
  model is upgraded. The eval is the rubric, not the literal.
- **Per-PR eval in CI.** Cost (Sonnet judge x 5 scenarios is ~$0.50
  per PR) and nondeterminism (the same prompt scores 4.1 on one run,
  4.3 on the next) would make the gate noisy and expensive. Evals are
  a release tool, not a per-commit tool. See `docs/DECISIONS.md`
  ADR-013.
- **End-to-end "the dashboard renders correctly" assertions.** Those
  are covered by manual demo rehearsal and the unit tests on
  `/health` + `/ready`. Per `AGENTS.md` §11 we do not write further
  integration or component tests.

## Datasets

Hand-labelled JSON files live in `apps/api/tests/evals/data/`:

- `router_labels.json` — 50 messages in hardware-team voice
- `scoring_scenarios.json` — 20 (member, message) pairs with expected
  relative rank
- `rag_questions.json` + `rag_corpus/*.md` — 30 questions and 8
  Markdown documents (ECO, FAI report, firmware notes, supplier
  strategy, DVT exit plan, gripper risk, EMC pre-scan, phase gate)
- `digest_scenarios.json` — 5 (member + project + top-N scored items)
  contexts, plus expected critical topics for the judge

The judge rubric is at `apps/api/tests/evals/judge_prompts/digest_rubric.txt`.

## When the numbers will be revisited

- After a model upgrade (Sonnet 4.6 -> 4.7): re-baseline once, document
  the delta.
- After a prompt change in `routing/prompts/`, `digest/prompts/`, or
  `cards/prompts/`: re-run the affected eval, update the printed
  table here if the new number is the new baseline.
- After a scoring weight change in `scoring/weights.py`: re-run
  `make eval-scoring`.
- After a chunker change in `rag/chunker.py`: re-run `make eval-rag`.

A run cadence of "weekly + on tag" is the right rhythm. Daily is too
expensive; only-on-demand lets regressions land unnoticed.
