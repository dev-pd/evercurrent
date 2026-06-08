"""Mock-drive ingest entrypoint.

`mock_drive_ingest(local_path, org_id, project_id)` reads a local PDF
and feeds it through the same `ingest_pdf_path` task the live Drive
path uses. Used by the demo + by the unit tests.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import structlog

from evercurrent.ingestion.tasks import ingest_pdf_path
from evercurrent.rag.embedder import EmbeddingProvider

log = structlog.get_logger(__name__)


def _ensure_exists(path: Path) -> None:
    """Sync exists() check kept out of the async path for ASYNC240."""
    if not path.exists():
        msg = f"mock_drive_ingest: {path} not found"
        raise FileNotFoundError(msg)


async def mock_drive_ingest(
    *,
    local_path: Path,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    external_id: str | None = None,
    title: str | None = None,
    embedder: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    """Read a local PDF and run the same ingest pipeline as the live path.

    `project_id` is accepted for symmetry with the live path; the task
    itself resolves an `org_id`-owned project when none is wired into
    the documents row directly. The argument is kept in the signature
    so callers can stay forward-compatible when we introduce per-doc
    project targeting.
    """
    path = Path(local_path)
    _ensure_exists(path)
    used_external_id = external_id or f"mock:{path.name}"
    used_title = title or path.stem
    log.info(
        "drive.mock.ingest",
        path=str(path),
        org_id=str(org_id),
        project_id=str(project_id),
    )
    return await ingest_pdf_path(
        org_id=org_id,
        source="drive",
        external_id=used_external_id,
        title=used_title,
        pdf_path=path,
        kind_hint="pdf",
        embedder=embedder,
    )
