"""SSE serialiser for AgentEvent."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from evercurrent.agent.runner import AgentEvent


def encode_sse(event: AgentEvent) -> str:
    """Encode one AgentEvent as a single SSE message."""
    return f"event: {event.type}\ndata: {json.dumps(event.payload)}\n\n"


async def stream_to_sse(events: AsyncIterator[AgentEvent]) -> AsyncIterator[bytes]:
    """Pipe an AgentEvent stream through SSE encoding."""
    yield b": ping\n\n"  # initial keepalive
    async for event in events:
        yield encode_sse(event).encode()
    yield b"event: close\ndata: {}\n\n"
