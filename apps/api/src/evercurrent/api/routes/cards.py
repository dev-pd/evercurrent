from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from evercurrent.auth.deps import CurrentUserDep, SessionDep
from evercurrent.cards import repository as cards_repo
from evercurrent.cards.schemas import (
    CardPage,
    CardResponse,
)

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=CardPage)
async def list_cards(
    session: SessionDep,
    _user: CurrentUserDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CardPage:
    return await cards_repo.list_cards(
        session,
        project_id=project_id,
        kind=kind,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: uuid.UUID,
    session: SessionDep,
    _user: CurrentUserDep,
) -> CardResponse:
    card = await cards_repo.get_card(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="card not found",
        )
    return card
