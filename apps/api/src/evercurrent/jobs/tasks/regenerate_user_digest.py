"""Stubbed pending Phase 8."""

from __future__ import annotations

from typing import Any


async def regenerate_user_digest(
    _ctx: dict[str, Any],
    project_id: str,
    user_id: str,
    day: int,
    phase: str | None = None,
) -> dict[str, Any]:
    _ = project_id, user_id, day, phase
    raise NotImplementedError("Phase 8 rewrites digest generation")
