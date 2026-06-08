# CLAUDE.md

@AGENTS.md

## Claude Code specific

- **Authoritative build plan: `docs/phases/`.** Each phase is one
  doc with goal, files, tasks, test plan, definition of done. Read
  `docs/phases/README.md` first; it indexes everything.
- **Reference docs.** Read in this order when you need context:
  1. `docs/PRD.md` — what we build (plain-English walkthrough)
  2. `docs/SYSTEM_DESIGN.md` — data model, APIs, services
  3. `docs/AGENT_VS_WORKFLOW.md` — how agents fit
  4. `docs/DECISIONS.md` — every architectural choice with rationale
  5. `docs/MIGRATION.md` — file-by-file keep/rewrite/delete from old code
  6. `docs/TESTING_STRATEGY.md` — TDD + eval patterns
- **Subphase workflow.** Read the phase doc, restate the goal in
  one sentence, list files to touch, wait for `go`, implement, run
  `make lint`, verify definition of done, commit with
  `feat(phase-N): <description>`. Stop. Do not auto-start the next
  phase.
- **`EVERCURRENT_BUILD_DOC.md` is historical.** Pre-pivot plan. Do
  not read it unless explicitly asked; it conflicts with the new
  phases/ tree.
- When stuck, prefer using the `planner` subagent over guessing.
  (`Use the planner subagent to think through how to ...`)
- For frequent operations (new route, new component, new task, new
  prompt, new migration), check `.claude/skills/` first.
- Path-scoped rules in `.claude/rules/` auto-load on matching
  files (`apps/api/**/*.py`, `apps/web/**/*.{ts,tsx}`).

## Anti-patterns

- Do not add `Co-Authored-By: Claude` to commits. Attribution is
  empty by design in `.claude/settings.json`.
- Do not silently expand scope. If the phase doc is ambiguous, ask.
- Do not introduce new dependencies without justification. The
  locked versions in `pyproject.toml` and `package.json` are
  deliberate.
- Do not write comments that explain what the code does. Comments
  are only for explaining why something non-obvious was done.
- Do not skip the test plan in a phase. TDD on deterministic code
  is enforced — write the failing test first. See
  `docs/TESTING_STRATEGY.md`.

## When the phase doc and reality disagree

If you discover the doc is wrong about a version, an API
signature, or a library behaviour, stop and report it. We update
the doc together. Do not silently work around it.
