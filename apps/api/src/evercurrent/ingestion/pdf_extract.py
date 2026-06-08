"""PyMuPDF-based PDF text + position extractor.

PyMuPDF returns blocks in reading order with a per-block bounding box.
Each block we surface holds enough info for downstream chunking + a
future "highlight the citation on the embedded viewer" UX.

PyMuPDF (`fitz`) is an optional install — see PHASE_10 deps note. We
guard the import so the module can be linted + type-checked without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

log = structlog.get_logger(__name__)

MIN_BLOCK_CHARS = 20
_BLOCK_TUPLE_MIN_LEN = 5


@dataclass(frozen=True)
class Block:
    """One block from a PDF page. `bbox` is (x0, y0, x1, y1)."""

    page: int
    bbox: tuple[float, float, float, float]
    text: str


class PDFDependencyError(RuntimeError):
    """Raised when PyMuPDF (`fitz`) is not installed."""


if TYPE_CHECKING:
    fitz: Any = None
else:  # pragma: no cover - import guard, exercised at runtime
    try:
        import fitz
    except ImportError:  # pragma: no cover
        fitz = None


def _ensure_fitz() -> Any:
    if fitz is None:
        msg = (
            "PyMuPDF (`fitz`) is not installed. Add `pymupdf` to "
            "apps/api/pyproject.toml to enable PDF ingest."
        )
        raise PDFDependencyError(msg)
    return fitz


def extract_blocks(pdf_source: bytes | Path | str) -> list[Block]:
    """Extract blocks from a PDF. Skips blocks below MIN_BLOCK_CHARS.

    Accepts raw bytes (Drive download) or a path (mock-drive path).
    """
    mod = _ensure_fitz()
    if isinstance(pdf_source, (str, Path)):
        doc = mod.open(str(pdf_source))
    else:
        doc = mod.open(stream=pdf_source, filetype="pdf")

    out: list[Block] = []
    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            raw_blocks = page.get_text("blocks") or []
            for raw in raw_blocks:
                # PyMuPDF block tuple: (x0, y0, x1, y1, text, block_no, block_type)
                if len(raw) < _BLOCK_TUPLE_MIN_LEN:
                    continue
                x0, y0, x1, y1, text = raw[0], raw[1], raw[2], raw[3], raw[4]
                if not isinstance(text, str):
                    continue
                cleaned = text.strip()
                if len(cleaned) < MIN_BLOCK_CHARS:
                    continue
                out.append(
                    Block(
                        page=page_index + 1,
                        bbox=(float(x0), float(y0), float(x1), float(y1)),
                        text=cleaned,
                    ),
                )
    finally:
        doc.close()

    log.info("pdf.extract.done", blocks=len(out))
    return out
