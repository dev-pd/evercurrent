"""Background Dropbox sync, triggered by the Dropbox webhook on file changes.

Re-lists the connector's folder and ingests new/changed PDFs (dedup by path +
content rev), so a freshly added spec doc flows in without a manual Sync.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from evercurrent.config import get_settings
from evercurrent.connectors.dropbox.sync import sync_folder as dropbox_sync_folder
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db.session import admin_session_scope

log = structlog.get_logger(__name__)


async def sync_dropbox_connector(_ctx: dict[str, Any], connector_id: str) -> dict[str, Any]:
    settings = get_settings()
    vault = TokenVault(settings.connector_secret_key)
    cid = uuid.UUID(connector_id)
    async with admin_session_scope() as session:
        try:
            result = await dropbox_sync_folder(
                session=session,
                settings=settings,
                vault=vault,
                connector_id=cid,
                folder_path="",
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.warning("dropbox.webhook.sync_failed", connector_id=connector_id, error=str(exc))
            return {"status": "failed", "error": str(exc)}
    log.info("dropbox.webhook.synced", connector_id=connector_id, **result)
    return {"status": "ok", **result}
