"""Maps each task tier to a model: tagging -> Haiku; digest/doc-gen/agent ->
Sonnet. Keeps model-id choices in one place instead of scattered across callers."""

from __future__ import annotations

from enum import StrEnum

from evercurrent.config import get_settings


class ModelTier(StrEnum):
    TAGGING = "tagging"
    DIGEST = "digest"
    AGENT = "agent"
    DOC_GEN = "doc_gen"


def model_for(tier: ModelTier) -> str:
    settings = get_settings()
    haiku = settings.anthropic_model_haiku
    sonnet = settings.anthropic_model_sonnet
    return {
        ModelTier.TAGGING: haiku,
        ModelTier.DIGEST: sonnet,
        ModelTier.AGENT: sonnet,
        ModelTier.DOC_GEN: sonnet,
    }[tier]
