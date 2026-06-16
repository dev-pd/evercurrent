from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemberSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    display_name: str
    eng_role: str | None
    owned_subsystems: list[str] = Field(default_factory=list)


class MeProfile(BaseModel):
    model_config = ConfigDict(strict=True)

    org_name: str
    branding: dict[str, Any] = Field(default_factory=dict)
    role: str
