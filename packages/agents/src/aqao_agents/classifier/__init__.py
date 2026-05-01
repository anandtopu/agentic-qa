"""Failure Classifier — Epic 1.7.

Two-stage classifier:

1. :func:`heuristic.classify` — regex / structural rule pack that
   handles the obvious patterns (network timeout, 5xx, selector-not-found,
   etc.) without an LLM call. Story 1.7.1 AC: ≥30% of failures classified
   pre-LLM.

2. :class:`LlmClassifier` — falls through to an LLM call (MID tier) for
   the remainder. Story 1.7.2 AC: ≥75% accuracy on the bootstrap gold
   set; confidence calibrated.

The :class:`FailureClassifierAgent` chains them and emits a single
:class:`Classification` per signal.
"""

from aqao_agents.classifier.agent import (
    FailureClassifierAgent,
    FailureClassifierOutput,
)
from aqao_agents.classifier.heuristic import (
    HeuristicClassifier,
    HeuristicMatch,
)
from aqao_agents.classifier.llm import LlmClassifier
from aqao_agents.classifier.schema import (
    Classification,
    ClassificationSource,
    FailureCategory,
    FailureSignal,
)

__all__ = [
    "Classification",
    "ClassificationSource",
    "FailureCategory",
    "FailureClassifierAgent",
    "FailureClassifierOutput",
    "FailureSignal",
    "HeuristicClassifier",
    "HeuristicMatch",
    "LlmClassifier",
]
