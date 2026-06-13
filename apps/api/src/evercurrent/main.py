from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from evercurrent.api.middleware import RequestIDMiddleware
from evercurrent.api.routes.cards import router as cards_router
from evercurrent.api.routes.connectors import router as connectors_router
from evercurrent.api.routes.digests import router as digests_router
from evercurrent.api.routes.documents import router as documents_router
from evercurrent.api.routes.events import router as events_router
from evercurrent.api.routes.focus import router as focus_router
from evercurrent.api.routes.insights import router as insights_router
from evercurrent.api.routes.jobs import router as jobs_router
from evercurrent.api.routes.me import router as me_router
from evercurrent.api.routes.members import router as members_router
from evercurrent.api.routes.projects import router as projects_router
from evercurrent.api.routes.subscriptions import router as subscriptions_router
from evercurrent.api.routes.timeline import router as timeline_router
from evercurrent.api.routes.today import router as today_router
from evercurrent.api.routes.webhooks import router as webhooks_router
from evercurrent.auth.auth0 import Auth0Verifier
from evercurrent.config import get_settings
from evercurrent.db.session import dispose_engine, get_sessionmaker, init_engine
from evercurrent.tenancy.middleware import TenancyLoggingMiddleware


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _configure_logging(settings.log_level)
    init_engine()
    if settings.auth0_domain:
        app.state.auth0_verifier = Auth0Verifier(
            domain=settings.auth0_domain,
            audience=settings.auth0_audience,
        )
    else:
        app.state.auth0_verifier = None
    try:
        yield
    finally:
        verifier: Auth0Verifier | None = app.state.auth0_verifier
        if verifier is not None:
            await verifier.aclose()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EverCurrent API",
        version="0.1.0",
        description="Agentic AI layer for hardware engineering teams.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TenancyLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def ready() -> dict[str, object]:
        checks: dict[str, str] = {"db": "skipped", "redis": "skipped"}
        with contextlib.suppress(Exception):
            sm = get_sessionmaker()
            async with sm() as session:
                await session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        return {"status": "ok", "checks": checks}

    app.include_router(me_router)
    app.include_router(members_router)
    app.include_router(focus_router)
    app.include_router(webhooks_router)
    app.include_router(projects_router)
    app.include_router(digests_router)
    app.include_router(documents_router)
    app.include_router(events_router)
    app.include_router(jobs_router)
    app.include_router(today_router)
    app.include_router(timeline_router)
    app.include_router(connectors_router)
    app.include_router(cards_router)
    app.include_router(insights_router)
    app.include_router(subscriptions_router)

    Instrumentator(
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
