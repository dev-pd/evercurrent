from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from evercurrent.config import get_settings

router = APIRouter(prefix="/api/v1/events", tags=["events"])

_KEEPALIVE_SECONDS = 15.0


async def _stream(project_id: uuid.UUID) -> AsyncIterator[bytes]:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    pubsub = redis.pubsub()
    channel = f"events:{project_id}"
    await pubsub.subscribe(channel)

    yield b": connected\n\n"

    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=None),
                    timeout=_KEEPALIVE_SECONDS,
                )
            except (TimeoutError, RedisTimeoutError):
                yield b": keepalive\n\n"
                continue
            if message is None:
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            elif not isinstance(data, str):
                data = str(data)
            yield f"data: {data}\n\n".encode()
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
