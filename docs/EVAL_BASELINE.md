# EverCurrent — Eval Baseline

`make eval` runs the scoring + determinism suite against committed
seed data with the default weights and the prompts in
`apps/api/src/evercurrent/{enrichment,digest,decisions}/prompts/`.

## Scoring engine

| Metric                   | Result            | Notes                              |
|--------------------------|-------------------|------------------------------------|
| Scenarios passing top-1  | **6 / 6**         | `tests/evals/data/scoring_scenarios.json` |
| Determinism (10 / 100)   | **stable**        | identical rankings across runs     |

Covered: pure role match, cross-functional dependency match (synonym
map), phase weight shift (DVT → PVT), per-user feedback override,
critical urgency dominating role + dep, firmware-specific role.
Investigation triggers: any scenario regression > 0; non-determinism
(state leak in scoring).

## RAG retrieval (forward work)

Voyage free-tier (3 RPM) exceeds our retry budget. Attach a payment
method to dash.voyageai.com or wait between batches.

| Metric            | Target  | Notes                                       |
|-------------------|---------|---------------------------------------------|
| Precision @ 5     | ≥ 0.85  | doc-kind hit in top 5                       |
| MRR               | ≥ 0.70  | first matching chunk rank, 1/N              |
| Keyword presence  | ≥ 0.80  | expected_keywords present in top-1 chunk    |

Eval data file `tests/evals/data/rag_qa.json` to be populated with
12+ question/source pairs.

## Digest quality (LLM-as-judge, forward work)

Sonnet against a 4-dimension rubric — personalisation, prioritisation,
actionability, citation accuracy. Target each ≥ 4.0 / 5 averaged
across 3-5 personas. Citation accuracy also checked programmatically
(parse `[msg_<id>]` references against the source set the user saw).

Today's digests are LLM-generated and personalisation is empirically
visible — Sarah Chen leads with the ECO-178 thread she authored,
Mei Tanaka leads with AlumWest sourcing. Quantifying it via judge is
the next eval iteration.

## Decision extraction

Sonnet produces ~5 decisions per day. Confidence range 0.45–0.95.
Field-accuracy / hallucination rate metrics will be added with a
hand-labelled `decision_truth.json` in the next eval iteration.

Today the only structural assertion is: every extracted decision
cites at least one real message id from the corresponding day's
message bucket. Violations would surface as `decisions.invalid_entry`
warnings in the worker log.

## Reproducing the numbers

```bash
cp .env.example .env   # fill ANTHROPIC_API_KEY (+ VOYAGE_API_KEY for RAG)
make up                # postgres + redis + api + worker + beat + web + nginx
make migrate
make seed              # historical days 1-5
# The Celery beat scheduler starts immediately:
#  - refresh_today @ 30s: enrich -> digest -> extract decisions for
#    project.current_day (rolled forward to wall-clock today)
#  - synthesize_today_message @ 60s: Sonnet writes 2 phase-scoped
#    messages
# After a few minutes you'll have today's digest cache + ongoing flow.
make eval              # scoring + determinism (fast, no LLM, no keys)
```

`make eval` does NOT run end-to-end LLM / embedding evals by default
— that's reserved for the forward-work entries above. The default
suite is fast, deterministic, and runs without API keys.

## When to investigate

- Scoring regression > 0 scenarios → check `scoring/engine.py` or
  `scoring/weights.py` (likely a weight was tuned).
- Digest citation accuracy < 0.95 → check
  `digest/prompts/generate.txt` citation instructions and the
  `[msg_XXX]` extraction logic in `digest-card.tsx::humaniseCitations`.
- Decision recall < 0.7 → revisit `decisions/prompts/extract.txt`
  (the confidence floor at 0.4 may be dropping borderline truths).
- RAG P@5 < 0.85 → likely a chunker change. Inspect `rag/chunker.py`
  and re-baseline with `make ingest-docs`.
