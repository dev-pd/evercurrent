"""Model tiering: which Claude model handles which workload."""

from __future__ import annotations

from enum import StrEnum

from evercurrent.config import get_settings


class ModelTier(StrEnum):
    TAGGING = "tagging"
    DIGEST = "digest"
    DECISIONS = "decisions"
    AGENT = "agent"
    DOC_GEN = "doc_gen"


def model_for(tier: ModelTier) -> str:
    settings = get_settings()
    haiku = settings.anthropic_model_haiku
    sonnet = settings.anthropic_model_sonnet
    return {
        ModelTier.TAGGING: haiku,
        ModelTier.DIGEST: sonnet,
        ModelTier.DECISIONS: sonnet,
        ModelTier.AGENT: sonnet,
        ModelTier.DOC_GEN: sonnet,
    }[tier]
