"""Per-user, per-message relevance scoring.

Pure Python. Six signals (role, subsystem, urgency, phase, topic, cross-fn)
combined as a weighted sum and clamped to `[0, 1]`. Repository writes the
result to the `scores` table for read-cheap dashboard queries.
"""

from evercurrent.scoring.engine import score
from evercurrent.scoring.schemas import ScoreInput, ScoreResult
from evercurrent.scoring.weights import DEFAULT_WEIGHTS, WEIGHTS, Weights, default_weights

__all__ = [
    "DEFAULT_WEIGHTS",
    "WEIGHTS",
    "ScoreInput",
    "ScoreResult",
    "Weights",
    "default_weights",
    "score",
]
