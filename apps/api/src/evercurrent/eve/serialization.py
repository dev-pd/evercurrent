"""Serialize MCP tool results into JSON-able values for tool_result blocks."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively coerce dataclasses / Pydantic models / UUIDs into JSON types."""
    if isinstance(obj, list):
        return [to_jsonable(o) for o in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj
