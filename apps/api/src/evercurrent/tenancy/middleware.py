"""Tenancy middleware.

The auth dependency sets `request.state.org_id` after JWT verification.
This middleware is a thin observability hook — it binds the org context
into structlog so every log line carries `org_id`. RLS itself is set
by `auth.deps.get_session` because the session must be bound to the
event-loop coroutine that uses it.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class TenancyLoggingMiddleware(BaseHTTPMiddleware):
    """Binds org_id into structlog context for every request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        structlog.contextvars.clear_contextvars()
        org_id: uuid.UUID | None = getattr(request.state, "org_id", None)
        if org_id is not None:
            structlog.contextvars.bind_contextvars(org_id=str(org_id))
        return await call_next(request)
