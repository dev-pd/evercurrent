# CLAUDE.md

@AGENTS.md

## Claude Code specific

- **The code is the source of truth.** The step-by-step build is
  complete; read these for context when you need it:
  1. `docs/SYSTEM_DESIGN.md` — data model, APIs, services
  2. `docs/ARCHITECTURE.md` — design decisions and rationale
  3. `docs/AGENT_VS_WORKFLOW.md` — how agents fit (incl. Eve)
  4. `docs/DECISIONS.md` — every architectural choice with rationale
  5. `docs/PRD.md` — what we build (plain-English walkthrough)
  6. `docs/TESTING_STRATEGY.md` — TDD + eval patterns
- **Workflow.** Restate the goal in one sentence, list the files to
  touch, wait for `go`, implement, run `make lint`, verify, then
  commit with a Conventional Commit. Stop; don't auto-start the next
  task.
- When stuck, prefer using the `planner` subagent over guessing.
  (`Use the planner subagent to think through how to ...`)
- For frequent operations (new route, new component, new task, new
  prompt, new migration), check `.claude/skills/` first.
- Path-scoped rules in `.claude/rules/` auto-load on matching
  files (`apps/api/**/*.py`, `apps/web/**/*.{ts,tsx}`).

## Anti-patterns

- Do not add `Co-Authored-By: Claude` to commits. Attribution is
  empty by design in `.claude/settings.json`.
- Do not silently expand scope. If the task is ambiguous, ask.
- Do not introduce new dependencies without justification. The
  locked versions in `pyproject.toml` and `package.json` are
  deliberate.
- Do not write comments that explain what the code does. Comments
  are only for explaining why something non-obvious was done.
- Do not skip the test plan. TDD on deterministic code is enforced —
  write the failing test first. See `docs/TESTING_STRATEGY.md`.

## When a doc and reality disagree

If you discover a doc is wrong about a version, an API signature, or
a library behaviour, stop and report it. We update the doc together.
Do not silently work around it.
