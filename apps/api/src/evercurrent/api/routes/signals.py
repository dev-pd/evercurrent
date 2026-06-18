"""Routes for signals: paginated list, detail with sources, and status updates."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.signals import repository as signals_repo
from evercurrent.signals.schemas import (
    SignalPage,
    SignalResponse,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=SignalPage)
async def list_signals(
    session: SessionDep,
    _user: CurrentUserDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SignalPage:
    return await signals_repo.list_signals(
        session,
        project_id=project_id,
        kind=kind,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: uuid.UUID,
    session: SessionDep,
    _user: CurrentUserDep,
) -> SignalResponse:
    signal = await signals_repo.get_signal(session, signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="signal not found",
        )
    return signal
