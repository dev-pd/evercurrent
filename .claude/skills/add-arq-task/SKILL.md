---
name: add-arq-task
description: |
  Use this skill when adding a new background job to the EverCurrent backend
  using Arq. Triggered when implementing tasks like enrich_messages,
  generate_digests, extract_decisions, advance_day, ingest_doc, or any
  scheduled/async work. Covers task signature, idempotency, error handling,
  worker registration, scheduling, and progress tracking.
---

# Add an Arq task

Use when adding a background job to `apps/api/src/evercurrent/jobs/tasks/`.

## When to use Arq vs a synchronous call

**Use Arq when:**
- The work takes more than ~200ms
- The work calls an LLM or external API
- The work can be deferred (user doesn't need to wait)
- The work needs retry semantics
- The work runs on a schedule

**Do NOT use Arq for:**
- Simple synchronous DB lookups
- Work that needs immediate response (use SSE streaming instead)

## Task structure

Every task lives in `apps/api/src/evercurrent/jobs/tasks/<task_name>.py`
and follows this shape:

```python
"""Generate per-user digests for a given day."""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.session import session_factory
from evercurrent.digest import generator as digest_generator
from evercurrent.scoring import engine as scoring_engine

log = structlog.get_logger()


async def generate_user_digest(
    ctx: dict[str, Any],
    *,
    user_id: UUID,
    day: int,
) -> dict[str, Any]:
    """Score messages and generate digest for one user.

    Idempotent: if a digest already exists for (user_id, day), it is
    overwritten.

    Returns a dict with the new digest id and message count.
    """
    log.info("digest.generate.start", user_id=str(user_id), day=day)

    async with session_factory() as session:
        scored = await scoring_engine.score_all_for_user(
            session=session, user_id=user_id, day=day
        )
        digest = await digest_generator.generate(
            session=session, user_id=user_id, day=day, scored=scored
        )
        await session.commit()

    log.info(
        "digest.generate.done",
        user_id=str(user_id),
        day=day,
        digest_id=str(digest.id),
        item_count=len(digest.item_message_ids),
    )
    return {"digest_id": str(digest.id), "item_count": len(digest.item_message_ids)}
```

Key points:

- **First positional arg is `ctx: dict[str, Any]`.** Arq passes the
  worker context (Redis pool, etc.). Even if unused, it must be there.
- **All other args are keyword-only** (`*,`).
- **Each call creates its own `AsyncSession`** via `session_factory()`.
  Tasks do not share sessions with web requests.
- **structlog with task name as the event prefix:**
  `digest.generate.start`, `digest.generate.done`, `digest.generate.error`.
- **Idempotent.** Re-running the same task with the same args should
  produce the same result (or be a no-op).

## Worker registration

In `apps/api/src/evercurrent/jobs/worker.py`:

```python
from arq.connections import RedisSettings

from evercurrent.config import settings
from evercurrent.jobs.tasks import (
    advance_day,
    enrich_messages,
    extract_decisions,
    generate_digests,
    ingest_doc,
)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        enrich_messages.enrich_day,
        generate_digests.generate_user_digest,
        generate_digests.generate_all_digests,
        extract_decisions.extract_decisions_for_day,
        advance_day.advance_day,
        ingest_doc.ingest_document,
    ]
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # 1 hour
```

## Enqueuing a task from a route

```python
from arq import ArqRedis
from fastapi import APIRouter, Depends

from evercurrent.api import deps


@router.post("/digests/generate")
async def post_generate_digests(
    day: int,
    redis: ArqRedis = Depends(deps.get_arq_pool),
) -> dict[str, str]:
    job = await redis.enqueue_job("generate_all_digests", day=day)
    return {"job_id": job.job_id, "status": "queued"}
```

## Retry semantics

Arq retries failed jobs by default. For idempotency safety:

- Use a unique `_job_id` if you want to dedupe enqueues:
  `await redis.enqueue_job("...", _job_id=f"digest:{user_id}:{day}")`
- Tasks should be safe to retry: they should not double-write, double-bill,
  or duplicate side effects.
- For LLM calls, retries are fine; you'll just pay twice in the worst
  case. Log token costs to spot this.

## Scheduling

For periodic work (e.g. "every day at 9am"):

```python
from arq import cron

class WorkerSettings:
    cron_jobs = [
        cron(
            generate_digests.generate_all_digests,
            hour=9,
            minute=0,
            kwargs={"day": "auto"},  # task figures out current day
        ),
    ]
```

For our take-home, the "advance day" button manually triggers
`advance_day` — we don't actually need wall-clock scheduling. The cron
example is for future production behavior.

## Composing tasks

For multi-step workflows like `advance_day`, enqueue child tasks:

```python
async def advance_day(ctx: dict[str, Any]) -> dict[str, Any]:
    new_day = await projects_service.advance_day(...)

    redis: ArqRedis = ctx["redis"]
    await redis.enqueue_job("enrich_day", day=new_day, _job_id=f"enrich:{new_day}")
    # Wait for enrich to finish, then chain. For our take-home, sequential
    # await of helper functions is also fine — avoid Arq job chaining
    # complexity if the steps are short enough to run in one task.

    return {"new_day": new_day}
```

For our take-home, prefer awaiting service functions sequentially within
one task rather than enqueueing many small jobs. Simpler and avoids
multi-job orchestration concerns.

## Error handling

- Let unexpected exceptions propagate. Arq will retry per `max_tries`.
- Catch and log expected failures (e.g. Anthropic 429 rate limit, retried
  internally by httpx + tenacity).
- For non-recoverable errors (bad input), raise a custom exception that
  Arq won't retry: implement `class FatalJobError(Exception)` and check
  for it in a custom retry policy if needed.

## Observability

Every task should emit at minimum:

- `<task>.start` with relevant input args
- `<task>.done` with output summary (counts, ids, latency)
- `<task>.error` with exception class on failure (Arq logs this anyway, but
  explicit is better for searching)

If the task uses an LLM, also log token counts.

## Checklist before considering a task done

- [ ] Function signature: `ctx: dict[str, Any], *, <kwargs>`
- [ ] Own `AsyncSession` via `session_factory()`
- [ ] Idempotent
- [ ] structlog start/done/error events
- [ ] Registered in `WorkerSettings.functions`
- [ ] At least one place enqueues it (route, cron, or another task)
- [ ] Test enqueue + execute end-to-end manually (`curl` to trigger, then
      `docker compose logs worker` to verify)

## Common mistakes

- Sharing `AsyncSession` between the enqueuing route and the task (sessions
  are not picklable, will crash).
- Forgetting to register the task in `WorkerSettings`.
- Non-idempotent side effects (sending an email twice on retry).
- Tasks that take longer than `job_timeout`.
