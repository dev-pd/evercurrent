# EverCurrent — Eval Baseline

`make eval` runs the suite. Numbers below were collected against the
committed seed data (Phase 1.4/1.5) with the default scoring weights and
the prompts in `apps/api/src/evercurrent/{enrichment,digest,decisions}/prompts/`.

## Scoring engine

| Metric                   | Result            | Notes                              |
|--------------------------|-------------------|------------------------------------|
| Scenarios passing top-1  | **6 / 6**         | `tests/evals/data/scoring_scenarios.json` |
| Determinism (10 / 100)   | **stable**        | identical rankings across runs     |

What's covered: pure role match, cross-functional dependency match
(synonym map), phase weight shift (DVT → PVT), per-user feedback weight
override, critical urgency dominating role+dep, firmware-specific role.
What would trigger investigation: any scenario regression > 0; ranking
non-determinism (would indicate a state leak in scoring).

## RAG retrieval

Not yet runnable end-to-end without a paid Voyage tier — free-tier 3 RPM
exceeds our retry budget. With a payment method attached and
`make ingest-docs` complete:

| Metric            | Target  | Notes                                       |
|-------------------|---------|---------------------------------------------|
| Precision @ 5     | ≥ 0.85  | doc-kind hit in top 5                       |
| MRR               | ≥ 0.70  | first matching chunk rank, 1/N              |
| Keyword presence  | ≥ 0.80  | expected_keywords present in top-1 chunk    |

Eval data at `tests/evals/data/rag_qa.json` (to be populated in next
iteration with 12+ question/source pairs).

## Digest quality (LLM-as-judge)

Driven by Sonnet against a 4-dimension rubric: personalisation,
prioritisation, actionability, citation accuracy. Run with
`ANTHROPIC_API_KEY` set; targets each ≥ 4.0 / 5 averaged across 3-5
personas. Citation accuracy is also checked programmatically (parse
`[msg_XXX]` and assert each id exists in the source set the user saw).

Current digests for day 1-5 across 8 users were generated via Sonnet
4.6; spot-checks on Sarah / Mei / David digests show personalisation
working — Sarah's leads with ECO-178 (which she authored), Mei's with
the AlumWest sourcing path.

## Decision extraction

| Day | Decisions written | Notes                                                                    |
|-----|--------------------|--------------------------------------------------------------------------|
| 1   | 5                  | thermal failure investigation, supplier strike risk                      |
| 2   | 3                  | bracket FEA outcome, AlumWest engagement                                 |
| 3   | 5                  | ECO-178 draft + signoffs + sourcing                                      |
| 4   | 5                  | ECO-178 approval, BMS hysteresis patch, gripper resonance characterise   |
| 5   | 5                  | DVT exit posture, firmware skip-band, PVT cost ladder                    |

23 decisions total. Confidence range 0.45–0.95. Field-accuracy /
hallucination metrics will be added with a hand-labelled `decision_truth.json`
in the next iteration.

## Reproducing the numbers

```bash
cp .env.example .env   # fill ANTHROPIC_API_KEY (+ VOYAGE_API_KEY for RAG)
make up
make migrate
make seed
docker compose exec -T api python -c "
import asyncio
from evercurrent.db.session import session_scope
from evercurrent.db.repositories import ProjectRepository
from evercurrent.jobs.tasks.enrich_messages import enrich_day
from evercurrent.digest.generator import generate_all_digests_for_day
from evercurrent.decisions.extractor import extract_decisions_for_day
async def m():
    async with session_scope() as s:
        p = await ProjectRepository(s).get_by_name('Warehouse Robot v2')
    for day in (1,2,3,4,5):
        await enrich_day({}, str(p.id), day)
        await extract_decisions_for_day(p.id, day)
        await generate_all_digests_for_day(p.id, day)
asyncio.run(m())
"
make eval
```

`make eval` does NOT run end-to-end LLM/embedding evals by default — it
runs the scoring + determinism scenarios that are fast, deterministic,
and don't require API keys. LLM/embedding evals are commented above as
forward work.

## When to investigate

- Scoring regression > 0 scenarios failing → check `scoring/engine.py`
  or `scoring/weights.py` (likely the place a weight was tuned).
- Digest citation accuracy < 0.95 → check `digest/prompts/generate.txt`
  citation instructions and the `[msg_XXX]` extraction logic.
- Decision recall < 0.7 → revisit `decisions/prompts/extract.txt`
  (the confidence floor at 0.4 may be dropping borderline truths).
- RAG P@5 < 0.85 → likely a chunker change. Inspect
  `rag/chunker.py` and re-baseline with `make ingest-docs`.
