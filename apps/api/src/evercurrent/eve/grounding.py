"""Grounding gate: keep only insight sources whose snippet traces back to
evidence Eve actually retrieved through its tools. A snippet the model wrote
that matches nothing it saw is a fabrication, and is dropped."""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_OVERLAP = 0.6
_MIN_TOKENS = 3


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1}


def _is_grounded(snippet: str, evidence_tokens: list[set[str]]) -> bool:
    snip = _tokens(snippet)
    if len(snip) < _MIN_TOKENS:
        return False
    for ev in evidence_tokens:
        if not ev:
            continue
        overlap = len(snip & ev) / len(snip)
        if overlap >= _MIN_OVERLAP:
            return True
    return False


def ground_sources(
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_tokens = [_tokens(str(e.get("snippet") or "")) for e in evidence]
    return [
        s for s in sources if _is_grounded(str(s.get("snippet") or ""), evidence_tokens)
    ]
