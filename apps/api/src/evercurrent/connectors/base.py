"""Connector Protocol: the provider-agnostic interface a source connector (Slack, Dropbox)
implements."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class Connector(Protocol):
    kind: str

    async def build_install_url(self, *, org_id: uuid.UUID) -> str: ...

    async def handle_oauth_callback(
        self,
        *,
        code: str,
        state: str,
    ) -> uuid.UUID: ...

    async def discover_channels(self, *, connector_id: uuid.UUID) -> int: ...

    async def backfill_channel(
        self,
        *,
        connector_channel_id: uuid.UUID,
        days: int,
    ) -> int: ...
