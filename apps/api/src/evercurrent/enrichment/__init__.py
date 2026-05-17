"""Message enrichment: topic, urgency, affected roles, entities.

Two implementations live here:
- `LLMTagger` calls Claude Haiku via the LLMProvider.
- `HeuristicTagger` is a deterministic rule-based fallback so the
  pipeline runs end-to-end without API keys (eval baseline + demos).
"""

from evercurrent.enrichment.schemas import MessageTagPayload
from evercurrent.enrichment.tagger import HeuristicTagger, LLMTagger, Tagger

__all__ = ["HeuristicTagger", "LLMTagger", "MessageTagPayload", "Tagger"]
