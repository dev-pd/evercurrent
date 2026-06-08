"""Digest generation — stubbed pending Phase 8.

Phase 7 rewrote scoring with a new function signature; the v1 LLM /
Heuristic generators below depended on the old `score_messages_for_user`.
Rather than refactor here only to throw it away, the module is stubbed.
A clean Sonnet-driven implementation lands in Phase 8.
"""

from __future__ import annotations

from typing import Any


def generate_all_digests(_arg: Any, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise NotImplementedError("Phase 8 rewrites digest generation")


__all__ = ["generate_all_digests"]
