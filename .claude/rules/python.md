---
paths:
  - "apps/api/**/*.py"
description: Python coding standards for the EverCurrent FastAPI backend
---

# Python rules (apps/api/)

Auto-loaded when editing any `.py` file under `apps/api/`. Codifies the
non-negotiables from `AGENTS.md` §6, plus operational specifics.

## Hard requirements

- **Type hints on every signature.** Parameters and return types. Including
  `-> None` for procedures.
- **No `Any` types.** If genuinely dynamic, use `# type: ignore[misc]` with a
  comment explaining why.
- **Pydantic v2 strict mode.** Every Pydantic model includes
  `model_config = ConfigDict(strict=True)`.
- **All I/O is async.** Database (asyncpg), Anthropic, Voyage, Redis (aioredis
  via `redis-py` 5+), HTTP (httpx async).
- **No `print()` statements.** Use `structlog`:
  ```python
  import structlog
  log = structlog.get_logger()
  log.info("digest.generated", user_id=str(user.id), day=day, token_cost=tc)
  ```
- **No bare `logging`.** Only structlog.
- **No raw `anthropic.AsyncAnthropic()` instantiation.** Go through
  `src/evercurrent/llm/client.py`.

## Project conventions

- **Module structure.** A service module like `scoring/` contains:
  - `__init__.py` — public exports only
  - `engine.py` or domain-named files for the core logic
  - `schemas.py` for Pydantic models specific to the module
  - `prompts/*.txt` for LLM prompts if applicable
- **Repositories return domain models.** Never SQLAlchemy models. Map
  in/out via dedicated functions.
- **FastAPI dependencies via `Depends(get_x)`** factory functions, not
  module-level globals.
- **Background work uses Arq.** Define tasks in `jobs/tasks/<name>.py`,
  register in `jobs/worker.py`. Tasks must be idempotent.

## Pydantic v2 patterns

- Prefer `Annotated` for field validation:
  ```python
  from typing import Annotated
  from pydantic import BaseModel, ConfigDict, Field

  class CreateMessage(BaseModel):
      model_config = ConfigDict(strict=True)
      text: Annotated[str, Field(min_length=1, max_length=10_000)]
      channel: Annotated[str, Field(pattern=r"^#[a-z0-9-]+$")]
  ```
- Use `model_validator(mode='after')` for cross-field validation.
- Pydantic `Settings` (from `pydantic-settings`) for all config. Loaded from
  environment in `src/evercurrent/config.py`.

## SQLAlchemy 2.0 async patterns

- `AsyncSession` only. Never sync sessions.
- Use `select()` with `await session.execute(stmt)`, not legacy query API.
- Eager load relationships explicitly via `selectinload()` or `joinedload()`
  to avoid N+1 queries.
- Repository methods take an `AsyncSession` parameter, do not create their
  own. Session lifecycle is managed by the route or worker.

## Anti-patterns Claude should not write

- `try/except: pass` — handle errors explicitly or let them propagate.
- `from x import *` — always explicit imports.
- Mutable default arguments (`def f(x: list = [])` — use `None` and check).
- Implicit string concatenation in lists.
- Comments that describe what the code does. Only comment WHY when the
  code's intent is non-obvious.
- Docstrings that are just a re-stating of the function name.

## When you're about to add a dependency

Stop. Check if it's listed in `pyproject.toml` already. If not, ask the user
before adding it. The locked stack is deliberate.

## Function and file size

- Functions over 50 lines: consider splitting.
- Files over 400 lines: consider splitting.
- Classes with more than 7 public methods: consider whether it should be
  two classes.

These are not laws, they are smells. Use judgment.
