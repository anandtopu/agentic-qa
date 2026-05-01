"""Scorer Protocol."""

from __future__ import annotations

from typing import Any, Protocol

from aqao_eval.types import EvalCase, ScoreResult


class Scorer(Protocol):
    """A pluggable scoring rule.

    ``dimension`` is the label written into the scorecard (e.g.
    ``"json_schema_valid"``, ``"category_accuracy"``). ``score`` returns
    a :class:`ScoreResult` whose ``score`` is in ``[0, 1]`` — fractional
    scores are allowed (e.g. partial-credit rubrics).
    """

    dimension: str

    def score(self, case: EvalCase, output: dict[str, Any]) -> ScoreResult: ...
