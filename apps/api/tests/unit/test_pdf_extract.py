"""Unit tests for the PyMuPDF-backed block extractor.

We synthesise a minimal PDF in-memory with PyMuPDF itself so the test
needs no committed binary fixture. The extractor is asserted to return
Block tuples with the (page, bbox, text) shape, and to drop blocks
under `MIN_BLOCK_CHARS`.

PyMuPDF is an optional install (see PHASE_10 deps note); the whole
module is skipped when it isn't available.
"""

from __future__ import annotations

import pytest

fitz = pytest.importorskip("fitz")

from evercurrent.ingestion.pdf_extract import (  # noqa: E402
    MIN_BLOCK_CHARS,
    Block,
    extract_blocks,
)


def _build_pdf(paragraphs: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for para in paragraphs:
        page.insert_text((72, y), para)
        y += 24
    blob = doc.write()
    doc.close()
    return blob


def test_extract_returns_blocks_with_page_and_bbox() -> None:
    long_para = "x" * (MIN_BLOCK_CHARS + 40)
    pdf_bytes = _build_pdf([long_para])

    blocks = extract_blocks(pdf_bytes)

    assert blocks, "expected at least one block"
    first = blocks[0]
    assert isinstance(first, Block)
    assert first.page == 1
    assert isinstance(first.bbox, tuple)
    assert len(first.bbox) == 4
    assert all(isinstance(x, float) for x in first.bbox)
    assert long_para in first.text


def test_short_blocks_are_skipped() -> None:
    pdf_bytes = _build_pdf(["short", "y" * (MIN_BLOCK_CHARS + 5)])

    blocks = extract_blocks(pdf_bytes)

    for block in blocks:
        assert len(block.text) >= MIN_BLOCK_CHARS
