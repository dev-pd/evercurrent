"""Paragraph-aware sliding-window chunker for PDF blocks.

Strategy:
- Walk blocks in reading order.
- A short, uppercase or title-cased block becomes the "current section
  heading" — subsequent chunks inherit it.
- Pack block texts into a window that targets `target_chars` size; when
  the window is full, emit it and start a new one whose first
  `overlap_chars` are the suffix of the previous chunk.
- The chunk knows its starting page (from the first block packed) so a
  future viewer can scroll to it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from evercurrent.ingestion.pdf_extract import Block

DEFAULT_TARGET_CHARS = 800
DEFAULT_OVERLAP_CHARS = 100
HEADING_MAX_CHARS = 80


@dataclass(frozen=True)
class Chunk:
    """One emitted chunk. `ordinal` increases monotonically from 0."""

    ordinal: int
    text: str
    section: str | None
    page_start: int


_HEADING_HINT_RE = re.compile(
    r"^(?:[A-Z0-9][A-Z0-9 \-/.&]+|\d+(?:\.\d+)*\s+.+|#{1,6}\s+.+)$",
)


def _looks_like_heading(text: str) -> bool:
    if len(text) > HEADING_MAX_CHARS:
        return False
    cleaned = text.strip()
    if not cleaned:
        return False
    if "\n" in cleaned:
        return False
    return _HEADING_HINT_RE.match(cleaned) is not None


def chunk_blocks(  # noqa: C901
    blocks: list[Block],
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """Chunk PDF blocks into Voyage-friendly windows.

    A heading-shaped block becomes the section name carried into following
    chunks. Headings are NOT included in the body text — they're metadata.
    """
    if target_chars <= 0:
        raise ValueError("target_chars must be > 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be >= 0")
    if overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be < target_chars")

    chunks: list[Chunk] = []
    ordinal = 0
    current_section: str | None = None
    buffer_text = ""
    buffer_page: int | None = None

    def emit(buf: str, page: int | None) -> None:
        nonlocal ordinal
        stripped = buf.strip()
        if not stripped:
            return
        chunks.append(
            Chunk(
                ordinal=ordinal,
                text=stripped,
                section=current_section,
                page_start=page if page is not None else 1,
            ),
        )
        ordinal += 1

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        if _looks_like_heading(text):
            # Flush pending buffer under the *old* section before
            # switching, so a heading boundary always closes a chunk.
            if buffer_text:
                emit(buffer_text, buffer_page)
                buffer_text = ""
                buffer_page = None
            current_section = text
            continue

        candidate = (buffer_text + "\n\n" + text) if buffer_text else text
        if len(candidate) <= target_chars:
            buffer_text = candidate
            if buffer_page is None:
                buffer_page = block.page
            continue

        # Emit what we have, then start a new buffer with overlap suffix.
        emit(buffer_text, buffer_page)
        tail = buffer_text[-overlap_chars:] if overlap_chars else ""
        buffer_text = (tail + "\n\n" + text) if tail else text
        buffer_page = block.page

    if buffer_text:
        emit(buffer_text, buffer_page)

    return chunks
