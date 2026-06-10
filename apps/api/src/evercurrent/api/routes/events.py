"""Server-Sent Events bridge.

Subscribes to `events:{project_id}` on Redis and relays every published
JSON message as an SSE `event: update` to the connected browser. Each
connection holds one async pubsub subscription; nginx already disables
proxy_buffering for /api/* so events flush immediately.

Production: this replaces the /today polling heartbeat. The Celery
worker publishes after every write; the API streams the push down to
each connected dashboard.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from evercurrent.config import get_settings

router = APIRouter(prefix="/api/v1/events", tags=["events"])

_KEEPALIVE_SECONDS = 15.0


async def _stream(project_id: uuid.UUID) -> AsyncIterator[bytes]:
    """Yield SSE-encoded events for a project's pubsub channel."""
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    pubsub = redis.pubsub()
    channel = f"events:{project_id}"
    await pubsub.subscribe(channel)

    # Hint to nginx/clients that the stream is open.
    yield b": connected\n\n"

    try:
        while True:
            # `get_message` returns None when no message is pending; loop
            # with periodic keepalive comments so idle connections don't
            # get killed by intermediary proxies.
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=None),
                    timeout=_KEEPALIVE_SECONDS,
                )
            except TimeoutError:
                yield b": keepalive\n\n"
                continue
            if message is None:
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            elif not isinstance(data, str):
                data = str(data)
            yield f"event: update\ndata: {data}\n\n".encode()
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()


@router.get("")
async def events(project_id: Annotated[uuid.UUID, Query()]) -> StreamingResponse:
    return StreamingResponse(
        _stream(project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
