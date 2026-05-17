# CLAUDE.md

@AGENTS.md

## Claude Code specific

- The authoritative build plan is `EVERCURRENT_BUILD_DOC.md`. Always read it
  before starting work.
- We execute the build doc phase by phase, subphase by subphase. Do not jump
  ahead. See `.claude/skills/execute-subphase/SKILL.md` for the workflow.
- When stuck, prefer using the `planner` subagent over guessing.
  (`Use the planner subagent to think through how to ...`)
- For frequent operations (new route, new component, new task, new prompt,
  new migration), check `.claude/skills/` first. There is likely a skill
  for it.
- Path-scoped rules in `.claude/rules/` auto-load when editing matching
  files. Python rules load on `apps/api/**/*.py`, TypeScript rules load
  on `apps/web/**/*.{ts,tsx}`.

## Anti-patterns

- Do not add `Co-Authored-By: Claude` to commits. Attribution is empty by
  design in `.claude/settings.json`.
- Do not silently expand scope. If the build doc is ambiguous, ask.
- Do not write tests in this project except (a) the eval harness under
  `apps/api/tests/evals/` and (b) unit tests for `/health` and `/ready`
  under `apps/api/tests/unit/`. Phase tasks that ask for other tests
  (scoring unit tests, end-to-end integration tests, Vitest, etc.) are
  superseded — skip them and note it in the commit. See AGENTS.md
  "Testing philosophy".
- Do not introduce new dependencies without justification. The locked
  versions in the build doc are deliberate.
- Do not write comments that explain what the code does. Comments are
  only for explaining why something non-obvious was done.

## When the build doc and reality disagree

If you discover the doc is wrong about a version, an API signature, or a
library behavior, stop and report it. We update the doc together. Do not
silently work around it.
