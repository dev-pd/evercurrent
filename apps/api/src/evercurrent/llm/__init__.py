"""LLM client wrapper + model tiering.

`client.LLMProvider` is the interface every other module uses.
`AnthropicProvider` is the real implementation. `tiering` decides which
model handles which workload (Haiku for tagging, Sonnet for everything
else). Test/eval code can substitute a fake provider that returns canned
responses.
"""

from evercurrent.llm.client import AnthropicProvider, LLMProvider, ToolSpec
from evercurrent.llm.tiering import ModelTier, model_for

__all__ = ["AnthropicProvider", "LLMProvider", "ModelTier", "ToolSpec", "model_for"]
