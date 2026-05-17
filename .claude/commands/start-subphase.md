---
description: Start work on a build doc subphase by number (e.g. /start-subphase 2.3)
---

# /start-subphase $ARGUMENTS

User wants to start subphase **$ARGUMENTS** of `EVERCURRENT_BUILD_DOC.md`.

Follow the workflow defined in `.claude/skills/execute-subphase/SKILL.md`:

1. Read the subphase $ARGUMENTS section from `EVERCURRENT_BUILD_DOC.md` in
   full (goal, tasks, definition of done, any sketches).
2. Confirm dependencies on prior subphases by running `git log --oneline -n 20`
   to see what's been completed.
3. Restate the subphase goal in one sentence and list files to create or
   modify.
4. Stop and wait for the user to reply `go` before writing any code.
5. After `go`: implement only what the subphase asks for.
6. After implementing: run `make lint` and verify the subphase's
   definition of done.
7. Commit with `feat(phase-$ARGUMENTS): <short description>`.
8. Stop. Do not auto-start the next subphase.

If $ARGUMENTS is not a valid subphase identifier (format: `N.M` like `2.3`),
ask the user to clarify which subphase they want.
