---
name: execute-subphase
description: |
  Use this skill when the user asks to implement a subphase from the build doc,
  e.g. "implement Phase 2.3", "let's do Phase 0.1", "start the next subphase",
  "continue with the build doc". Drives the disciplined subphase workflow:
  read the spec, restate, wait for go, implement, verify DoD, commit, stop.
---

# Execute subphase

When you are asked to implement a subphase from `docs/phases/`,
follow this workflow precisely. Do not deviate.

## Step 1: Read the subphase

Open the relevant `docs/phases/PHASE_N_*.md` and locate the subphase the
user named (e.g. "2.3"). Read in full:

- **Goal** — what this subphase achieves
- **Tasks** — concrete items
- **Definition of done** — verification criteria
- Any code sketches, prompt sketches, or schema fragments included

Also read any subphases this one depends on (typically the prior subphase in
the same phase). Know what already exists in the repo.

## Step 2: Read project context

Confirm you know:

- The current state of the repo (run `git status` and `git log --oneline -n 10`)
- The relevant module's existing code (`Read` or `Glob` the directory)
- Any rules that auto-loaded based on the files you will edit

## Step 3: Restate and plan

Output a structured response to the user:

```
**Subphase N.M goal:** <one sentence>

**Dependencies satisfied:** <yes/no, with notes if there are concerns>

**Files I will create:**
- path/to/new_file.py

**Files I will modify:**
- path/to/existing_file.py

**Approach:** <2-4 sentences describing how, referencing patterns from
existing modules where applicable>

**Open questions:** <only if there are real ambiguities; otherwise omit>

Ready to proceed. Reply `go` to start.
```

If there are open questions, STOP and wait for answers before proceeding.

## Step 4: Wait for `go`

Do not write any code before the user confirms. This is the most important
rule. The plan-then-execute discipline is the whole point of subphases.

## Step 5: Implement

Implement only what the subphase asks for. If you find yourself doing
something not in the task list, STOP and ask. Common reasons to stop:

- The subphase references a module that doesn't exist as expected
- A library API has changed since the build doc was written
- A coding standard from `AGENTS.md` would force a different approach
- An earlier subphase missed something needed here

Follow all rules from `AGENTS.md`, `.claude/rules/python.md`, and
`.claude/rules/typescript.md`.

## Step 6: Verify DoD

Run the verification checks for the subphase:

- For Python work: `cd apps/api && uv run ruff check && uv run ty check`
- For TypeScript work: `cd apps/web && pnpm lint && pnpm typecheck`
- For database changes: `cd apps/api && uv run alembic upgrade head`
- For API endpoints: `curl` the endpoint and verify response shape
- For UI changes: `pnpm dev` and verify visually (or note that visual
  verification is needed)

Each subphase's "Definition of done" lists specific checks. Run them all.
Report PASS or FAIL per check. If anything fails, fix it before claiming
the subphase is done.

## Step 7: Commit

Stage and commit with conventional commit format:

```bash
git add <relevant files>
git commit -m "feat(phase-N.M): <short description matching the subphase goal>"
```

For example:
- `feat(phase-0.1): repository bootstrap with both apps scaffolded`
- `feat(phase-2.3): scoring engine and weights`
- `feat(phase-8.2): RAG retrieval eval with precision@5 and MRR`

Do NOT add `Co-Authored-By: Claude` (attribution is empty in
`.claude/settings.json`).

## Step 8: Stop

Report what was done:

```
**Subphase N.M complete.**

- <bullet of what was built>
- <bullet of what was verified>

Committed as <short hash>. Ready for Phase N.(M+1) when you say go.
```

Do NOT auto-start the next subphase. Wait for the user.

## Failure modes to avoid

- **Scope creep:** doing more than the subphase asks. Stop and ask.
- **Skipping the restate step:** going straight to code. Always plan first.
- **Skipping verification:** claiming done without running the checks.
- **Skipping the commit:** leaving uncommitted changes between subphases.
- **Auto-continuing:** moving to the next subphase without user signal.

These five failures are the most common ways subphased workflows break.
Avoid them.
