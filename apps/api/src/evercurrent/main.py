"""FastAPI app factory and entrypoint for the EverCurrent backend.

Phase 0.x scope: minimal app exposing `/health` (liveness) and `/ready`
(readiness). Real DB/Redis dependency checks land in `/ready` once those
clients are wired (Phase 1+); for now both return a fixed shape so the
unit tests + docker healthchecks can rely on them.
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

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        # Real dependency probes (postgres + redis) land in Phase 1+ when
        # the clients are wired through lifespan.
        return {"status": "ok", "checks": {"db": "skipped", "redis": "skipped"}}

    return app


app = create_app()
