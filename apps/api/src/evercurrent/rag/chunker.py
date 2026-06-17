"""Splits markdown into overlapping, header-aware chunks sized for embedding."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_DEFAULT_MAX_TOKENS = 800
_DEFAULT_OVERLAP_TOKENS = 100
_TOKEN_RATIO = 4
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")

_HEADER_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    section_path: str | None = None
    chunk_index: int = 0


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // _TOKEN_RATIO)


def _recursive_split(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    if _approx_tokens(text) <= max_tokens:
        return [text]

    max_chars = max_tokens * _TOKEN_RATIO
    overlap_chars = overlap_tokens * _TOKEN_RATIO

    chunks: list[str] = []
    for sep in _SEPARATORS:
        if sep == "":
            stride = max(1, max_chars - overlap_chars)
            chunks.extend(text[i : i + max_chars] for i in range(0, len(text), stride))
            return [c for c in chunks if c.strip()]
        if sep in text:
            pieces = text.split(sep)
            current = ""
            for piece in pieces:
                candidate = current + (sep if current else "") + piece
                if _approx_tokens(candidate) <= max_tokens:
                    current = candidate
                    continue
                if current:
                    chunks.append(current)
                    tail = current[-overlap_chars:] if overlap_chars else ""
                    current = (tail + sep + piece) if tail else piece
                else:
                    chunks.extend(_recursive_split(piece, max_tokens, overlap_tokens))
                    current = ""
            if current:
                chunks.append(current)
            return [c for c in chunks if c.strip()]
    return [text]


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    breadcrumbs: dict[int, str] = {}
    last_end = 0
    pending_path = ""

    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))
        last_end = matches[0].start()

    for i, m in enumerate(matches):
        level = len(m.group("hashes"))
        title = m.group("title").strip()
        for lvl in list(breadcrumbs):
            if lvl >= level:
                del breadcrumbs[lvl]
        breadcrumbs[level] = title
        pending_path = " > ".join(breadcrumbs[k] for k in sorted(breadcrumbs))

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        last_end = body_end
        if body:
            sections.append((pending_path, body))
    _ = last_end
    return sections


def chunk_markdown(
    text: str,
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_index = 0
    for section_path, body in _split_into_sections(text):
        pieces: list[str]
        if _approx_tokens(body) <= max_tokens:
            pieces = [body]
        else:
            pieces = _recursive_split(body, max_tokens, overlap_tokens)
        for piece in pieces:
            stripped = piece.strip()
            if not stripped:
                continue
            chunks.append(
                Chunk(
                    text=stripped,
                    section_path=section_path or None,
                    chunk_index=chunk_index,
                    metadata={
                        "section_path": section_path,
                        "approx_tokens": _approx_tokens(stripped),
                    },
                ),
            )
            chunk_index += 1
    return chunks
