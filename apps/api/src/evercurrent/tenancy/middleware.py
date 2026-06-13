from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class TenancyLoggingMiddleware(BaseHTTPMiddleware):
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
