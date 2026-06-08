"""Connector protocol shared by all external data sources.

The protocol is intentionally narrow: every connector should be
installable via OAuth, list its channels, and accept a backfill
trigger. The Events-webhook pathway is connector-specific and
plumbed at the routes layer, not via this protocol.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class Connector(Protocol):
    """Minimum surface every connector implements.

    Implementations are not required to be classes — module-level
    callables that match these signatures satisfy the protocol.
    """

    kind: str

    async def build_install_url(self, *, org_id: uuid.UUID) -> str:
        """Return the OAuth consent URL the user should be redirected to."""
        ...

    async def handle_oauth_callback(
        self,
        *,
        code: str,
        state: str,
    ) -> uuid.UUID:
        """Exchange the OAuth `code` for tokens, persist, return connector id."""
        ...

    async def discover_channels(self, *, connector_id: uuid.UUID) -> int:
        """Discover channels available to this install. Returns count discovered."""
        ...

    async def backfill_channel(
        self,
        *,
        connector_channel_id: uuid.UUID,
        days: int,
    ) -> int:
        """Pull `days` of history for the channel. Returns count ingested."""
        ...
