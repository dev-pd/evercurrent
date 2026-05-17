"""FastAPI app factory and entrypoint for the EverCurrent backend."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from evercurrent.config import get_settings
from evercurrent.db.session import dispose_engine, get_sessionmaker, init_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_engine()
    try:
        yield
    finally:
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        checks: dict[str, str] = {"db": "skipped", "redis": "skipped"}
        with contextlib.suppress(Exception):
            sm = get_sessionmaker()
            async with sm() as session:
                await session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        return {"status": "ok", "checks": checks}

    return app


app = create_app()
