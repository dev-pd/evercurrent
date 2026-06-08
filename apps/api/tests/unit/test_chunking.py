"""Unit tests for the paragraph-aware sliding-window chunker.

The chunker is a pure function over `list[Block]`. We hand-build blocks
directly rather than going through PyMuPDF so this module stays free
of the optional `fitz` dependency.
"""

from __future__ import annotations

from evercurrent.ingestion.chunking import (
    DEFAULT_OVERLAP_CHARS,
    DEFAULT_TARGET_CHARS,
    chunk_blocks,
)
from evercurrent.ingestion.pdf_extract import Block


def _block(text: str, *, page: int = 1) -> Block:
    return Block(page=page, bbox=(0.0, 0.0, 100.0, 20.0), text=text)


def test_chunker_respects_target_chars() -> None:
    target = 400
    overlap = 50
    # Each block is small enough to fit the target individually; the
    # chunker packs them together but must flush at target.
    short = "short sentence. " * 4  # ~64 chars
    blocks = [_block(short) for _ in range(40)]

    chunks = chunk_blocks(blocks, target_chars=target, overlap_chars=overlap)

    assert chunks, "expected non-empty chunk list"
    assert len(chunks) >= 2, "expected multiple chunks under target"
    # Every chunk except possibly the last respects target + overlap + 2 slack.
    max_block_len = max(len(b.text) for b in blocks)
    for chunk in chunks[:-1]:
        assert len(chunk.text) <= target + overlap + max_block_len + 4


def test_chunker_respects_overlap() -> None:
    target = 150
    overlap = 40
    big = "abcdefghij" * 20  # 200 chars, will force a split
    blocks = [_block(big), _block(big)]

    chunks = chunk_blocks(blocks, target_chars=target, overlap_chars=overlap)

    assert len(chunks) >= 2
    prev_tail = chunks[0].text[-overlap:]
    assert prev_tail in chunks[1].text


def test_chunker_carries_section_heading() -> None:
    blocks = [
        _block("INTRODUCTION"),
        _block("This is a long paragraph under the introduction heading."),
        _block("RESULTS"),
        _block("Some results body text that lives under the results heading."),
    ]

    chunks = chunk_blocks(blocks, target_chars=DEFAULT_TARGET_CHARS, overlap_chars=20)

    assert chunks[0].section == "INTRODUCTION"
    assert any(c.section == "RESULTS" for c in chunks)


def test_chunker_handles_paragraph_smaller_than_overlap() -> None:
    target = 100
    overlap = 50
    blocks = [_block("short paragraph just under target size " * 2), _block("tiny tail")]

    chunks = chunk_blocks(blocks, target_chars=target, overlap_chars=overlap)

    assert chunks  # didn't crash
    assert any("tiny tail" in c.text for c in chunks)


def test_ordinals_are_sequential_from_zero() -> None:
    blocks = [_block("paragraph text " * 30) for _ in range(4)]

    chunks = chunk_blocks(
        blocks,
        target_chars=DEFAULT_TARGET_CHARS,
        overlap_chars=DEFAULT_OVERLAP_CHARS,
    )

    for i, chunk in enumerate(chunks):
        assert chunk.ordinal == i
