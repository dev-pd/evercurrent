"""Knowledge Cards: durable decisions / risks / open questions.

Cards are the atomic unit of awareness in EverCurrent. The Router
agent (Phase 5) flags messages that deserve a Card; the builder in
this module loads thread context, calls Sonnet to draft the Card
body, and persists `cards` + `card_sources` rows.

Public surface:
- `build_card(session, llm, ...)` — idempotent builder coroutine.
- `CardDraft` — Sonnet's structured-output schema.
"""

from __future__ import annotations

from evercurrent.cards.builder import build_card
from evercurrent.cards.schemas import CardDraft

__all__ = ["CardDraft", "build_card"]
