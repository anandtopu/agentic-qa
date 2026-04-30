"""Exact-match scorers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qaforge_eval.types import EvalCase, ScoreResult


@dataclass(slots=True)
class FieldExactMatchScorer:
    """1.0 iff ``output[field]`` equals ``case.expected[field]``."""

    field: str
    dimension: str = ""

    def __post_init__(self) -> None:
        if not self.dimension:
            self.dimension = f"exact_match:{self.field}"

    def score(self, case: EvalCase, output: dict[str, Any]) -> ScoreResult:
        expected = case.expected.get(self.field)
        actual = output.get(self.field)
        ok = expected == actual
        return ScoreResult(
            case_id=case.id,
            dimension=self.dimension,
            score=1.0 if ok else 0.0,
            rationale=(
                f"{self.field}={actual!r} matched expected"
                if ok
                else f"{self.field}={actual!r} != expected {expected!r}"
            ),
        )


@dataclass(slots=True)
class CategoricalAccuracyScorer:
    """Same as :class:`FieldExactMatchScorer` but with classifier semantics.

    The dimension defaults to ``category_accuracy``. The expected /
    actual fields default to ``"category"`` to match the failure
    classifier output.
    """

    expected_field: str = "category"
    actual_field: str = "category"
    dimension: str = "category_accuracy"

    def score(self, case: EvalCase, output: dict[str, Any]) -> ScoreResult:
        expected = case.expected.get(self.expected_field)
        actual = output.get(self.actual_field)
        ok = expected == actual
        return ScoreResult(
            case_id=case.id,
            dimension=self.dimension,
            score=1.0 if ok else 0.0,
            rationale=(
                f"category={actual!r} matched"
                if ok
                else f"category={actual!r} != expected {expected!r}"
            ),
        )
