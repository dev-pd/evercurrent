from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class Role(StrEnum):
    MECH_ENG = "mech_eng"
    EE = "ee"
    SUPPLY_CHAIN = "supply_chain"
    PM = "pm"
    QA = "qa"
    FIRMWARE = "firmware"
    PROCUREMENT = "procurement"


def _coerce_role(v: object) -> Role:
    if isinstance(v, Role):
        return v
    if isinstance(v, str):
        return Role(v)
    raise TypeError(f"cannot coerce {type(v).__name__} to Role")


RoleField = Annotated[Role, BeforeValidator(_coerce_role)]


class User(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    username: Annotated[str, Field(min_length=1, max_length=64)]
    display_name: Annotated[str, Field(min_length=1, max_length=128)]
    role: RoleField
    owned_subsystems: list[str] = Field(default_factory=list)
    owned_parts: list[str] = Field(default_factory=list)
    topic_weights: dict[str, float] = Field(default_factory=dict)
    created_at: dt.datetime
