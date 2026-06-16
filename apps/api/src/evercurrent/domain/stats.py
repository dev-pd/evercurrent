from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageActivity(BaseModel):
    model_config = ConfigDict(strict=True)

    count: int
    last_at: datetime | None
