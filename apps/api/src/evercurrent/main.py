"""FastAPI app factory and entrypoint for the EverCurrent backend."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from evercurrent.api.middleware import RequestIDMiddleware
from evercurrent.api.routes.agent import router as agent_router
from evercurrent.api.routes.decisions import router as decisions_router
from evercurrent.api.routes.digests import router as digests_router
from evercurrent.api.routes.feedback import router as feedback_router
from evercurrent.api.routes.projects import router as projects_router
from evercurrent.api.routes.users import router as users_router
from evercurrent.config import get_settings
from evercurrent.db.session import dispose_engine, get_sessionmaker, init_engine


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
    try:
        yield
    finally:
        pool = getattr(app.state, "arq_pool", None)
        if pool is not None:
            await pool.aclose()
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

    app.include_router(projects_router)
    app.include_router(users_router)
    app.include_router(digests_router)
    app.include_router(feedback_router)
    app.include_router(agent_router)
    app.include_router(decisions_router)

    return app


app = create_app()
