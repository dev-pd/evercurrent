"""Agent chat SSE endpoint."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from evercurrent.agent.runner import run_agent
from evercurrent.agent.streaming import stream_to_sse
from evercurrent.api.deps import CurrentUserId
from evercurrent.api.schemas import AgentChatRequest

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat")
async def chat(
    payload: AgentChatRequest,
    current_user_id: CurrentUserId,
    project_id: Annotated[uuid.UUID, Query()],
) -> StreamingResponse:
    if current_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Impersonate-User header is required",
        )
    events = run_agent(
        query=payload.query,
        project_id=project_id,
        user_id=current_user_id,
    )
    return StreamingResponse(
        stream_to_sse(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
