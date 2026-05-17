# EverCurrent — Demo Script

Five-minute walkthrough for a reviewer.

## Minute 1 — the framing

Hardware engineering teams have knowledge scattered across Slack,
MCAD, Jira, Confluence. A mech engineer doesn't read the supply chain
channel, but when a supplier strike hits the aluminum extrusion her
bracket needs, she needs to know today. EverCurrent's positioning is
cross-functional dependency tracking and decision extraction — not
generic summarisation. This prototype demonstrates both, plus a
6-tool reasoning agent over the same data.

## Minute 2 — personalisation

1. Open `http://localhost:8080/dashboard`.
2. Impersonation dropdown is preset to Sarah Chen (mech_eng, owns
   chassis + mounting + brackets).
3. Day 3 digest leads with:
   - **ECO-178 fast-track** (she authored).
   - **AL-7075-T6 sourcing** (her chassis subsystem, cost delta).
   - **Lin's testing plan** (test units cover her revised brackets).
4. Switch impersonation to Mei Tanaka (supply_chain, owns BOM +
   supplier_management).
5. Same underlying messages — different digest. Now leads with the
   AlumWest trial lot, the ExtruCo strike status, the cost premium
   absorption decision for PVT.

Drive home: same data, different digests, **driven by role +
cross-functional dependency match, scored deterministically before any
LLM rewrites it**.

## Minute 3 — phase awareness

1. With Sarah selected, switch project phase DVT → PVT via the
   dropdown.
2. Within 100ms the digest reshuffles toward production yield and
   supplier quality items.
3. This is governed by `scoring/weights.py` and the `phase_concerns`
   map in `seed_data/project.json`, NOT by re-asking the LLM.
   Predictable, cheap, testable — and exactly what a senior architect
   wants for a personalisation layer.

## Minute 4 — agentic chat

1. Open the right-side chat panel.
2. Ask **"What should I worry about this week?"**.
3. Watch the tool call cards stream in:
   `get_project_state` → `query_decisions` → `search_messages` →
   final text answer.
4. The model cites `[msg_<id>]`, `[doc:<title>]`, `[decision_<id>]` as
   it reasons across the three sources.
5. Follow up with **"What's the torque spec for the chassis motor?"**.
6. `search_documents` fires against the PRD; the answer cites
   `[doc:PRD §3]` with the torque figure.

Drive home: **multi-source reasoning**, not single-tool RAG.

## Minute 5 — eval rigor + production story

1. From a terminal: `make eval`. 6/6 scoring scenarios pass + 2
   determinism checks.
2. Show `docs/EVAL_BASELINE.md`: scoring P@1 = 6/6, decision counts
   per day, scoping for RAG / digest LLM-as-judge in the next
   iteration.
3. Open `docs/PRODUCTION_ROADMAP.md`. Walk through the top three
   sections in 30 seconds each:
   - **Real Slack adapter** behind the `IngestionAdapter` interface,
     OAuth + Events API + rate-limited backfill.
   - **ITAR / SOC 2** with regional endpoints, audit logs, PII
     redaction step around every LLM call.
   - **Observability**: per-tenant cost dashboard sliced by Haiku /
     Sonnet / Voyage. Nightly eval regression alerts.
4. Close: "The architecture decouples ingestion, enrichment, scoring,
   retrieval, and agent reasoning into independently testable
   services. Each layer can scale or be swapped without touching the
   others."

## Backup demos (if time allows)

- **Timeline view**: 5 days side-by-side for Sarah. You can see the
  dominant topic shift from "thermal failure" (days 1-2) to "ECO
  approval" (days 3-4) to "DVT exit + new gripper risk" (day 5).
- **Decisions log**: 23 structured decisions extracted by Sonnet,
  status badges, source message ids you can click back to.
- **Advance Day button**: triggers the full pipeline (enrich →
  decisions → digest) for the next day. Shows the worker doing real
  work.
