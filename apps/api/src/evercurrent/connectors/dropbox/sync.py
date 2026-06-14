from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.config import Settings
from evercurrent.connectors.dropbox.client import (
    DropboxAPIError,
    DropboxClient,
    FolderEntry,
    refresh_access_token,
)
from evercurrent.connectors.dropbox.install import decode_token_blob
from evercurrent.connectors.slack.crypto import TokenVault
from evercurrent.db import models
from evercurrent.ingestion.tasks import ingest_pdf_bytes

log = structlog.get_logger(__name__)

_TOKEN_REFRESH_SKEW_SECONDS = 60


async def ensure_fresh_dropbox_token(
    *,
    session: AsyncSession,
    settings: Settings,
    vault: TokenVault,
    connector: models.Connector,
) -> str:
    blob = decode_token_blob(vault.decrypt(connector.credentials_secret))
    expires_at = int(str(blob.get("expires_at", 0)))
    refresh = blob.get("refresh_token")
    if expires_at - int(time.time()) > _TOKEN_REFRESH_SKEW_SECONDS:
        return str(blob["access_token"])

    if not refresh or settings.dropbox_client_id is None or settings.dropbox_client_secret is None:
        return str(blob["access_token"])

    new_tokens = await refresh_access_token(
        refresh_token=str(refresh),
        client_id=settings.dropbox_client_id,
        client_secret=settings.dropbox_client_secret,
    )
    new_blob = {
        "access_token": new_tokens.access_token,
        "refresh_token": new_tokens.refresh_token or refresh,
        "expires_at": int(time.time()) + new_tokens.expires_in,
        "account_id": blob.get("account_id", ""),
    }
    connector.credentials_secret = vault.encrypt(
        __import__("json").dumps(new_blob, separators=(",", ":")),
    )
    await session.flush()
    return new_tokens.access_token


def _is_pdf(entry: FolderEntry) -> bool:
    return not entry.is_folder and entry.name.lower().endswith(".pdf")


async def _already_ingested(
    *,
    session: AsyncSession,
    external_id: str,
) -> bool:
    existing = await session.execute(
        select(models.Document.id).where(
            models.Document.source == "dropbox",
            models.Document.external_id == external_id,
        ),
    )
    return existing.first() is not None


async def sync_folder(
    *,
    session: AsyncSession,
    settings: Settings,
    vault: TokenVault,
    connector_id: uuid.UUID,
    folder_path: str,
) -> dict[str, Any]:
    connector = (
        await session.execute(
            select(models.Connector).where(models.Connector.id == connector_id),
        )
    ).scalar_one_or_none()
    if connector is None:
        raise ValueError(f"connector {connector_id} not found")

    access_token = await ensure_fresh_dropbox_token(
        session=session,
        settings=settings,
        vault=vault,
        connector=connector,
    )
    client = DropboxClient(access_token=access_token)

    try:
        entries = await client.list_folder(path=folder_path, recursive=True)
    except DropboxAPIError as exc:
        log.exception("dropbox.sync.list_failed", error=str(exc))
        raise

    pdf_entries = [e for e in entries if _is_pdf(e)]
    ingested = 0
    skipped = 0
    failed = 0

    for entry in pdf_entries:
        if await _already_ingested(session=session, external_id=entry.id):
            skipped += 1
            continue
        try:
            pdf_bytes = await client.download(path=entry.path_lower)
            await ingest_pdf_bytes(
                org_id=connector.org_id,
                source="dropbox",
                external_id=entry.id,
                title=entry.name,
                pdf_bytes=pdf_bytes,
            )
            ingested += 1
            log.info(
                "dropbox.sync.ingested",
                connector_id=str(connector_id),
                file=entry.name,
                size=len(pdf_bytes),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "dropbox.sync.file_failed",
                file=entry.name,
                error=str(exc),
            )
            failed += 1

    return {
        "total_pdfs": len(pdf_entries),
        "ingested": ingested,
        "skipped": skipped,
        "failed": failed,
    }
