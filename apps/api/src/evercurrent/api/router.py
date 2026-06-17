"""API version assembly. Each resource router owns only its own path
(`/me`, `/cards`); the version prefix lives here in one place, so bumping
to v2 is a single new aggregator, not 15 edits."""

from __future__ import annotations

from fastapi import APIRouter

from evercurrent.api.routes.cards import router as cards_router
from evercurrent.api.routes.connectors import router as connectors_router
from evercurrent.api.routes.digests import router as digests_router
from evercurrent.api.routes.documents import router as documents_router
from evercurrent.api.routes.events import router as events_router
from evercurrent.api.routes.insights import router as insights_router
from evercurrent.api.routes.jobs import router as jobs_router
from evercurrent.api.routes.me import router as me_router
from evercurrent.api.routes.members import router as members_router
from evercurrent.api.routes.projects import router as projects_router
from evercurrent.api.routes.subscriptions import router as subscriptions_router
from evercurrent.api.routes.timeline import router as timeline_router
from evercurrent.api.routes.today import router as today_router
from evercurrent.api.routes.webhooks import router as webhooks_router

_V1_ROUTERS = (
    me_router,
    members_router,
    webhooks_router,
    projects_router,
    digests_router,
    documents_router,
    events_router,
    jobs_router,
    today_router,
    timeline_router,
    connectors_router,
    cards_router,
    insights_router,
    subscriptions_router,
)

api_v1 = APIRouter(prefix="/api/v1")
for _r in _V1_ROUTERS:
    api_v1.include_router(_r)
