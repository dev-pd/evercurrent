"""Per-user relevance scoring.

Pure Python, no I/O. The engine takes already-enriched messages, the user
profile, and the project state and emits a ranked list. Weights live in
`weights.py` so they can be tuned without touching the algorithm.
"""

from evercurrent.scoring.engine import ScoredMessage, score_messages_for_user
from evercurrent.scoring.weights import Weights, default_weights

__all__ = ["ScoredMessage", "Weights", "default_weights", "score_messages_for_user"]
