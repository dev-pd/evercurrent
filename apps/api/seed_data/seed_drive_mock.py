# ruff: noqa: INP001
"""Demo seed: feed sample PDFs through `mock_drive_ingest`.

Usage:

    uv run --project apps/api python -m seed_data.seed_drive_mock \
        --org-id <uuid> --project-id <uuid>

Reads any `*.pdf` under `apps/api/seed_data/sample_pdfs/` and runs each
through the same `ingest_document` path the live Drive webhook uses.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import structlog

from evercurrent.connectors.drive.mock import mock_drive_ingest

log = structlog.get_logger(__name__)

DEFAULT_PDF_DIR = Path(__file__).parent / "sample_pdfs"


def _collect_pdfs(pdf_dir: Path) -> list[Path]:
    """Sync glob kept out of async to satisfy ASYNC240."""
    return sorted(pdf_dir.glob("*.pdf"))


async def _seed_all(*, org_id: uuid.UUID, project_id: uuid.UUID, pdf_dir: Path) -> int:
    pdfs = _collect_pdfs(pdf_dir)
    if not pdfs:
        log.warning("seed_drive_mock.no_pdfs", dir=str(pdf_dir))
        return 0
    count = 0
    for path in pdfs:
        try:
            result = await mock_drive_ingest(
                local_path=path,
                org_id=org_id,
                project_id=project_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("seed_drive_mock.failed", path=str(path), error=str(exc))
            continue
        log.info(
            "seed_drive_mock.ingested",
            path=str(path),
            document_id=result.get("document_id"),
            chunks=result.get("chunks", 0),
        )
        count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    args = parser.parse_args(argv)
    n = asyncio.run(
        _seed_all(
            org_id=uuid.UUID(args.org_id),
            project_id=uuid.UUID(args.project_id),
            pdf_dir=Path(args.pdf_dir),
        ),
    )
    log.info("seed_drive_mock.done", count=n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
