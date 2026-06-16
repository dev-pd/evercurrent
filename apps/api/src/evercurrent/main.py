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
from evercurrent.api.router import api_v1
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

    app.include_router(api_v1)

    Instrumentator(
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
