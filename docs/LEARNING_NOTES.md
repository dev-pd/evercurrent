# Learning notes — EverCurrent build

A running log of non-obvious things I learned building this. Light
on celebration, heavy on what I'd do differently.

## SQLAlchemy `metadata` is reserved

Declarative `Base.metadata` is the table registry. A model column
called `metadata` clobbers it and breaks autoload. I renamed the
Python attribute to `metadata_` (DB column still `metadata`), then
Pydantic strict + `from_attributes=True` reads `obj.metadata` (the
registry) instead of `obj.metadata_` (the column) and validation
explodes. Fixed by aliasing the Pydantic field:
`metadata: dict[...] = Field(default_factory=dict, alias="metadata_")`
with `populate_by_name=True`. Easy to miss; cost ~20 minutes.

## StrEnum + Pydantic strict mode

StrEnum instances ARE strings at the bytecode level. Pydantic v2
strict mode rejects "value" as not-an-instance-of-Urgency when reading
from an ORM column. Pattern: every domain enum field gets a
`BeforeValidator` that calls `Enum(value)`. Same trick for tz-naive
ISO strings → tz-aware datetime in the decision extractor schema.

## Voyage free tier kills batch indexing

3 RPM. Our retry backoff caps at 8s. Indexing 5 docs at 1 batch each
hits the limit on doc 4. With a payment method attached the standard
tier is 300 RPM and it's a non-issue. Worth either a CLI flag to
sleep 20s between batches or a payment-method check on startup.

## Agent tool-use loop needs the assistant's own tool_use turn

Initial implementation forgot to push the assistant's tool_use blocks
to the conversation. Anthropic's API requires `messages[i]` (assistant
tool_use) → `messages[i+1]` (user with tool_result blocks). Without
that the model loses track of what it called and either repeats
itself or hallucinates a tool name. Lesson: the message history is
the model's working memory; treat it that way.

## Strict ruff catches real things

`select = ["ALL"]` flagged: mutable default class attrs (`RUF012`),
deprecated `assert` in non-test (`S101`) — actually appropriate when
the assertion is asserting an invariant for a type narrower, but the
right answer is to write the narrowing explicitly. `PLR2004` magic
numbers in comparisons caught my `>= 12.0` digest bucket threshold,
which I'd hardcoded. Made me extract `_TOP_PRIORITY_SCORE`, which is
where it belonged anyway. The rule that hurts most is `TC003` — move
stdlib imports into `TYPE_CHECKING`. With SQLAlchemy declarative the
modules ARE used at runtime; you don't want the lazy form. Adding
`TC003` (+ TC001/TC002) to the ignore list is the right call.

## docker-only execution needs a dev image target

Production `apps/web/Dockerfile` ships only `.next/standalone` —
zero node_modules in the runtime layer. Lint, prettier, tsc need
node_modules. I added a `dev` target stage that keeps the install +
source, and a `web-dev` compose service in the `dev` profile so
`make lint` runs eslint inside docker against the right image.
Bind-mounting the host source over `/app` + named volumes for
`/app/node_modules` and `/app/.next` is the standard recipe and
worth doing on day one.

## pgvector index direction matters

Created the HNSW index with `vector_cosine_ops` because we query with
`<=>` (cosine distance). If you build the index with the wrong
opclass, queries silently skip the index and fall back to brute
force. Eval P@5 numbers would look fine but every query is slow.
Always sanity-check `EXPLAIN ANALYZE` after building a vector index.

## Tailwind v4 dropped `@tailwindcss/typography`

Default install doesn't include `prose` classes. Either install the
plugin or ship a small bespoke `.prose` ruleset in globals.css. Spent
5 minutes debugging why ReactMarkdown output rendered as one wall of
text.

## Arq dedup on completed results bit us

Arq's `enqueue_job(_job_id=...)` skips the enqueue if a result for that
id already exists in Redis. We used a deterministic
`regen:{project}:{user}:{day}:{phase}` id to dedup spam-clicks — but
that also broke re-clicks after the first success. The user clicked
Regenerate again, Arq saw the previous result, returned without
running, the dashboard saw "complete" instantly + invalidated the
digest query, refetch returned the same content. Looked like the
button did nothing.

Fixed by migrating to Celery, which doesn't dedup against completed
results — every `.delay()` call gets a fresh UUID task_id. Click
spam is debounced client-side via `disabled={isPending}` instead.

Larger lesson: queue dedup semantics live at the boundary of "what
the user expects to happen on a second click". If the answer is "yes,
do it again, content may differ", dedup keys are the wrong tool.

## SSE > polling, but only when there's something to push

First pass had `/today` polling every 10s + a 30s digest refetch.
Worked, fine for one user. Second pass moved to SSE: Celery task
publishes to Redis pub/sub, FastAPI subscribes, browser EventSource
receives. Network traffic dropped to near-zero at idle; the dashboard
still updates within 50ms of the worker finishing.

The gotcha is the keepalive. EventSource will silently drop a
connection that's been idle for too long if anything in the path
(nginx, ALB, ELB) decides the socket is dead. The fix is a
`: keepalive\n\n` comment frame from the relay every 15s. Cheap on
the server, invisible to the client.

## Per-(user, day, phase) precompute beats on-demand regen

Phase swap on the UI used to trigger a synchronous LLM call.
~3-10s lag every click. The fix: precompute every cell at seed
(`make precompute-digests`, ~336 Sonnet calls). Phase swap becomes a
single Postgres write + one cached SELECT. Cells that haven't been
precomputed get a queued cold-start with a clear UI banner ("Showing
cached X while Y is queued").

Cost ~$1.70 per project at full precompute. Trivially recouped by
not paying for an LLM call on every click.

## Calendar-date rollover from a cron task

Mapping "today" to `project.current_day = (today - start_date) + 1`
sounds simple but the bookkeeping matters. We do it inside
`refresh_today` every 30s — first thing the task does is reconcile
`current_day` with wall-clock today. That way:

- A worker restart after midnight automatically catches up.
- Tests can freeze time + override `start_date` to drive any day.
- The UI labels everything by `start_date + (day - 1)` so the int
  is purely an internal handle.

## Heuristic fallback paid off twice

When the reviewer runs without API keys: enrichment falls back to
keyword tagging, digest falls back to template markdown, decisions
return empty (skipped). The dashboard still loads, the scoring eval
still passes 6/6. Without that fallback the demo would 500 on every
page without keys. Two hours of work, infinite future-proofing.

## What I'd do differently next time

- Pin Voyage payment-method check at startup; don't wait for the
  first batch to fail. A single `voyage.embed(["ping"])` in lifespan
  produces a clean error message at the right moment.
- Write the eval scenarios FIRST, then tune the scoring weights to
  pass them. I did it the other way and one scenario flushed out a
  latent design choice (critical urgency vs role match) that I had
  to make explicit by bumping the critical weight.
- The agent's `since` filter takes ISO datetime. The model loves to
  pass `2025-01-13` instead of `2026-05-14`. The fix is to put the
  current project day's anchor timestamp in the system prompt so the
  model doesn't guess.
