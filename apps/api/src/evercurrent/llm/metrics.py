"""Prometheus counters for LLM usage. Registered on the default registry, so
they appear at the /metrics endpoint the instrumentator already exposes."""

from __future__ import annotations

from prometheus_client import Counter

# Approximate Anthropic list prices, USD per 1M tokens (input, output).
# Estimates for dashboarding, not billing.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "haiku": (1.0, 5.0),
    "sonnet": (3.0, 15.0),
}

llm_tokens_total = Counter(
    "llm_tokens_total",
    "LLM tokens consumed",
    ["tier", "direction"],
)
llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Estimated LLM cost in USD",
    ["tier"],
)


def _price_for(model: str) -> tuple[float, float]:
    for key, price in _PRICE_PER_MTOK.items():
        if key in model:
            return price
    return (0.0, 0.0)


def record_llm_usage(model: str, tier: str, input_tokens: int, output_tokens: int) -> None:
    llm_tokens_total.labels(tier, "input").inc(input_tokens)
    llm_tokens_total.labels(tier, "output").inc(output_tokens)
    price_in, price_out = _price_for(model)
    cost = input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out
    llm_cost_usd_total.labels(tier).inc(cost)
