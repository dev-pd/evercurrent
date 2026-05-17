---
name: add-fastapi-route
description: |
  Use this skill when adding a new FastAPI route or endpoint to the EverCurrent
  backend, including: new GET/POST/PATCH/DELETE endpoints, new SSE streaming
  endpoints, new sub-routers under apps/api/src/evercurrent/api/routes/.
  Covers the layered route → service → repository pattern, Pydantic request
  and response schemas, dependency injection wiring, and error handling.
---

# Add a FastAPI route

Use when adding a new endpoint to `apps/api/src/evercurrent/api/routes/`.

## The layered pattern (non-negotiable)

```
HTTP request
    ↓
api/routes/<resource>.py    ← route handler, Pydantic schemas, status codes
    ↓ Depends()
api/deps.py                  ← dependency wiring (get_db_session, etc.)
    ↓
<service>/<module>.py        ← business logic
    ↓
db/repositories/<resource>.py ← data access
    ↓
SQLAlchemy session
```

A route handler must NEVER:
- Execute SQL directly
- Construct SQLAlchemy queries
- Call the Anthropic client directly
- Contain business logic

A route handler MUST:
- Validate input via a Pydantic request model
- Return a Pydantic response model
- Use `Depends()` for collaborators
- Map domain exceptions to HTTP responses (let middleware handle most)

## Step-by-step

### 1. Define request/response schemas

In `api/schemas.py` (or co-located in the route file if truly local):

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated
from uuid import UUID

class FeedbackRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: UUID
    message_id: UUID
    signal: Annotated[int, Field(ge=-1, le=1)]

class FeedbackResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    feedback_id: UUID
    new_weight: float
```

### 2. Define or extend the service

In `<service>/<module>.py`:

```python
async def record_feedback(
    *,
    session: AsyncSession,
    user_id: UUID,
    message_id: UUID,
    signal: int,
) -> FeedbackResult:
    """Record user feedback and update topic weights.

    Returns the new weight for the affected topic.
    """
    # business logic here
    ...
```

Service functions take collaborators (session, clients) as keyword-only
args. Return domain models, never schemas.

### 3. Define the route handler

In `api/routes/feedback.py`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.api import deps
from evercurrent.api.schemas import FeedbackRequest, FeedbackResponse
from evercurrent.feedback import service as feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_feedback(
    request: FeedbackRequest,
    session: AsyncSession = Depends(deps.get_db_session),
) -> FeedbackResponse:
    result = await feedback_service.record_feedback(
        session=session,
        user_id=request.user_id,
        message_id=request.message_id,
        signal=request.signal,
    )
    return FeedbackResponse(
        feedback_id=result.id,
        new_weight=result.new_weight,
    )
```

### 4. Mount the router

In `api/__init__.py` or wherever the API is assembled:

```python
from evercurrent.api.routes import feedback

app.include_router(feedback.router, prefix="/api/v1")
```

### 5. Handle errors

- Validation errors are handled by FastAPI automatically (422 with detail).
- Domain exceptions should be defined in `<service>/exceptions.py` and
  mapped to HTTP responses by an exception handler in `api/errors.py`.
- Never raise raw `HTTPException` from the service layer. Service raises
  domain exceptions; route handler converts (or middleware handles them
  globally).

### 6. SSE streaming endpoints

For SSE (used by the agent chat), the response is a
`StreamingResponse` with `media_type="text/event-stream"`:

```python
from fastapi.responses import StreamingResponse

@router.post("/chat")
async def post_chat(
    request: ChatRequest,
    session: AsyncSession = Depends(deps.get_db_session),
    impersonate_user_id: UUID = Depends(deps.get_impersonated_user_id),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in agent_runner.run(...):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Include a heartbeat every 15s to prevent client/proxy timeouts.

## Checklist before considering a route done

- [ ] Pydantic request/response models with strict mode
- [ ] Route handler under 30 lines (no business logic)
- [ ] Service function does the actual work
- [ ] Uses `Depends()` for all collaborators
- [ ] Router mounted in app assembly
- [ ] `curl` against the endpoint returns expected shape
- [ ] OpenAPI docs at `/docs` show the new endpoint correctly
- [ ] No SQL or Anthropic client calls in the route file

## Common mistakes

- Putting business logic in the route handler. Move to service.
- Returning a SQLAlchemy model from a route. Always Pydantic.
- Forgetting to await an async call.
- Using `@router.get` with a Pydantic body (use query params, headers, or
  `Body(...)` with POST).
