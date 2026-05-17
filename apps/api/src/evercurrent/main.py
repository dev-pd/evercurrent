"""FastAPI app factory and entrypoint for the EverCurrent backend.

Phase 0.1 scope: minimal app exposing `/health`. Subsequent phases wire
DB/Redis lifespan, middleware, routers, and a real `/ready` check.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="EverCurrent API",
        version="0.1.0",
        description="Agentic AI layer for hardware engineering teams.",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
