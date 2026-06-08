# Phases — build plan

The take-home gets built in 13 ordered phases. Each phase = one
self-contained chunk of work, one git branch, one commit, one phase
doc you can read in 5 minutes.

## How to read this directory

Each `PHASE_N_*.md` file has the same template:

1. **Goal** — one sentence
2. **Why this phase, this order** — what it depends on, why now
3. **Pre-requisites** — which earlier phases must be done
4. **Files touched** — exact list (new / modified / deleted)
5. **Tasks** — numbered, in order
6. **Test plan** — TDD: what tests come BEFORE the code
7. **Definition of done** — checklist
8. **Common pitfalls** — what's likely to go wrong
9. **Recap — what you'll be able to explain** — interview-ready
10. **Talking points (for the grill)** — pre-loaded answers

## Phase order + dependencies

```
0  RESET            ──▶  1  INFRA
                             │
                             ▼
                          2  AUTH (Auth0 + orgs + RLS)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           3 SLACK        4 MCP           (Phase 9 FE can start
              │              │             once 4-6 are done)
              ▼              │
           5 ROUTER ◀────────┘
              │
              ▼
           6 CARDS  ──▶  7 SCORING  ──▶  8 DIGEST
                                            │
                                            ▼
                                         9 DASHBOARD (FE)
                                            │
                                            ▼
                                         10 DRIVE/PDF
                                            │
                                            ▼
                                         11 NOTIFY (Slack DM)
                                            │
                                            ▼
                                         12 POLISH + EVALS
```

## Take-home scope (must ship)

Phases 0 → 11. Phase 12 is "if time."

## Stretch (only if all above land with days to spare)

- Linker agent (cross-source edges + impact preview)
- Timeline (Gantt with what-if)
- Audit log page

## Roadmap (explicitly NOT built, documented as "next")

- Chat agent (interactive Q&A)
- Phase agent ("ready for gate exit?")
- Personalizer agent (weekly feedback re-weighting)
- GitHub + Jira + Email connectors
- AWS production deploy
- Grafana dashboards + alerting

## Conventions every phase follows

- **TDD on deterministic code.** Write the failing test first. See
  `docs/TESTING_STRATEGY.md`.
- **Commit at end of phase.** Format: `feat(phase-N): <short>`.
- **Lint clean before commit.** `make lint`.
- **One branch per phase.** Format: `feat/phase-N-<short>`.
- **Phase doc is law.** If something isn't in the doc, don't do it.
  If you find you need to, stop and ask.

## Phases

| # | Title | Stack | Effort |
|---|-------|-------|--------|
| 0 | [Reset](PHASE_0_RESET.md) | git, delete dead code | 0.5 d |
| 1 | [Infra](PHASE_1_INFRA.md) | docker-compose, plugins, pre-commit, CI | 1 d |
| 2 | [Auth + tenancy](PHASE_2_AUTH.md) | Auth0, RLS, orgs, memberships | 1 d |
| 3 | [Slack ingest](PHASE_3_SLACK.md) | Slack OAuth, Events webhook, raw_events | 1.5 d |
| 4 | [MCP tool layer](PHASE_4_MCP.md) | FastMCP server + first tools | 0.5 d |
| 5 | [Router agent](PHASE_5_ROUTER.md) | Haiku, message_tags, Pydantic schemas | 1 d |
| 6 | [Cards](PHASE_6_CARDS.md) | cards + card_sources + builder | 1 d |
| 7 | [Scoring](PHASE_7_SCORING.md) | pure-Python score engine (TDD-heavy) | 0.5 d |
| 8 | [Digest agent](PHASE_8_DIGEST.md) | Sonnet, Celery Beat, prompt + schema | 1 d |
| 9 | [Dashboard FE](PHASE_9_DASHBOARD.md) | Next.js + Auth0 + TanStack + SSE | 1.5 d |
| 10 | [Drive + PDF ingest](PHASE_10_DRIVE.md) | Drive watch, PyMuPDF, Voyage embed | 1.5 d |
| 11 | [Notify (Slack DM)](PHASE_11_NOTIFY.md) | chat.postMessage, quiet hours | 0.5 d |
| 12 | [Polish + evals + demo](PHASE_12_POLISH.md) | eval harness, README, demo script | 1 d |

Total: ~12 days of focused work. Realistic in 7-10 calendar days.
