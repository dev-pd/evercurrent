# CLAUDE.md

@AGENTS.md

## Claude Code specific

- **The code is the source of truth.** The step-by-step build is
  complete. `docs/ARCHITECTURE.md` covers the backend architecture and
  rationale; everything else is recoverable from git history.
- **Workflow.** Restate the goal in one sentence, list the files to
  touch, wait for `go`, implement, run `make lint`, verify, then
  commit with a Conventional Commit. Stop; don't auto-start the next
  task.
- Code conventions are split by app: `apps/api/AGENTS.md` (backend) and
  `apps/web/AGENTS.md` (frontend, incl. the Next.js breaking-change warning).
  Each auto-loads with its subtree via a nested `CLAUDE.md`.

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
  write the failing test first (`apps/api/tests/`).

## When a doc and reality disagree

If you discover a doc is wrong about a version, an API signature, or
a library behaviour, stop and report it. We update the doc together.
Do not silently work around it.
