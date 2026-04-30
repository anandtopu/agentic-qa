"""Built-in scorers.

Every scorer implements :class:`Scorer` — ``dimension`` (label that ends
up on the scorecard) plus :meth:`score` returning a :class:`ScoreResult`
with a value in ``[0, 1]``. Scorers are deterministic (same inputs →
same score) so the same dataset run twice produces byte-identical
scorecards modulo timestamps.
"""

from qaforge_eval.scorers.base import Scorer
from qaforge_eval.scorers.budget import CostBudgetScorer, LatencyBudgetScorer
from qaforge_eval.scorers.exact import (
    CategoricalAccuracyScorer,
    FieldExactMatchScorer,
)
from qaforge_eval.scorers.schema import JsonSchemaValidScorer

__all__ = [
    "CategoricalAccuracyScorer",
    "CostBudgetScorer",
    "FieldExactMatchScorer",
    "JsonSchemaValidScorer",
    "LatencyBudgetScorer",
    "Scorer",
]
