from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Digest(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    project_member_id: uuid.UUID
    day_index: Annotated[int, Field(ge=0)]
    phase: Annotated[str, Field(min_length=1, max_length=64)]
    content_md: str
    card_ids: list[uuid.UUID] = Field(default_factory=list)
    message_ids: list[uuid.UUID] = Field(default_factory=list)
    generated_at: dt.datetime
