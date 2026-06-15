from __future__ import annotations

import sys
from typing import TypedDict


class Baseline(TypedDict):
    name: str
    metric: str
    target: float


BASELINES: dict[str, Baseline] = {
    "router_topic": {"name": "router_topic", "metric": "accuracy", "target": 0.85},
    "router_urgency": {"name": "router_urgency", "metric": "accuracy", "target": 0.90},
    "router_entities": {"name": "router_entities", "metric": "jaccard", "target": 0.60},
    "router_affected_roles": {
        "name": "router_affected_roles",
        "metric": "jaccard",
        "target": 0.70,
    },
    "router_should_create_card": {
        "name": "router_should_create_card",
        "metric": "accuracy",
        "target": 0.85,
    },
    "scoring_rank_correlation": {
        "name": "scoring_rank_correlation",
        "metric": "spearman",
        "target": 0.80,
    },
    "rag_precision_at_5": {
        "name": "rag_precision_at_5",
        "metric": "precision@5",
        "target": 0.70,
    },
    "rag_mrr": {"name": "rag_mrr", "metric": "mrr", "target": 0.55},
    "digest_relevance": {"name": "digest_relevance", "metric": "mean", "target": 4.0},
    "digest_citation_correctness": {
        "name": "digest_citation_correctness",
        "metric": "mean",
        "target": 4.0,
    },
    "digest_voice_second_person": {
        "name": "digest_voice_second_person",
        "metric": "mean",
        "target": 4.0,
    },
    "digest_length_budget": {
        "name": "digest_length_budget",
        "metric": "mean",
        "target": 4.0,
    },
    "eve_recall": {"name": "eve_recall", "metric": "recall", "target": 0.80},
    "eve_precision": {"name": "eve_precision", "metric": "precision", "target": 0.80},
    "eve_faithfulness": {
        "name": "eve_faithfulness",
        "metric": "mean",
        "target": 4.0,
    },
    "eve_relevance": {"name": "eve_relevance", "metric": "mean", "target": 4.0},
}


def warn_if_below_baseline(name: str, observed: float) -> bool:
    spec = BASELINES.get(name)
    if spec is None:
        print(f"[eval-baseline] no baseline registered for {name}", file=sys.stderr)
        return False
    if observed < spec["target"]:
        print(
            f"[eval-baseline] {name}: observed {observed:.3f} "
            f"< baseline {spec['target']:.2f} ({spec['metric']})",
            file=sys.stderr,
        )
        return False
    return True


def jaccard(a: list[str], b: list[str]) -> float:
    sa = {str(x).strip().lower() for x in a if str(x).strip()}
    sb = {str(x).strip().lower() for x in b if str(x).strip()}
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    if union == 0:
        return 1.0
    return inter / union


def precision_at_k(retrieved: list[str], expected: list[str], k: int = 5) -> float:
    if k <= 0:
        return 0.0
    expected_set = set(expected)
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for r in top_k if r in expected_set)
    return hits / k


def mean_reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for idx, item in enumerate(retrieved, start=1):
        if item in expected_set:
            return 1.0 / idx
    return 0.0


def spearman_rho(expected: list[int], actual: list[int]) -> float:
    if len(expected) != len(actual):
        msg = "expected and actual must be the same length"
        raise ValueError(msg)
    n = len(expected)
    if n < 2:
        return 1.0

    def _ranks(values: list[float]) -> list[float]:
        sorted_idx = sorted(range(n), key=lambda i: values[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[sorted_idx[j + 1]] == values[sorted_idx[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[sorted_idx[k]] = avg_rank
            i = j + 1
        return ranks

    rx = _ranks([float(v) for v in expected])
    ry = _ranks([float(v) for v in actual])
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    den_x = sum((r - mean_x) ** 2 for r in rx)
    den_y = sum((r - mean_y) ** 2 for r in ry)
    denom = (den_x * den_y) ** 0.5
    if denom == 0.0:
        return 0.0
    return num / denom
