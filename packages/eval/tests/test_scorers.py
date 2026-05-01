"""Unit tests for the built-in scorers — Story 2.6.2."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from aqao_eval.scorers import (
    CategoricalAccuracyScorer,
    CostBudgetScorer,
    FieldExactMatchScorer,
    JsonSchemaValidScorer,
    LatencyBudgetScorer,
)
from aqao_eval.types import EvalCase


def _case(expected: dict[str, object] | None = None, **kwargs: object) -> EvalCase:
    return EvalCase(
        id=str(kwargs.pop("id", "c1")),
        inputs={"x": 1},
        expected=expected or {"answer": "yes"},
    )


def test_field_exact_match_pass() -> None:
    scorer = FieldExactMatchScorer(field="answer")
    result = scorer.score(_case(), {"answer": "yes"})
    assert result.score == 1.0
    assert result.dimension == "exact_match:answer"


def test_field_exact_match_fail() -> None:
    scorer = FieldExactMatchScorer(field="answer")
    result = scorer.score(_case(), {"answer": "no"})
    assert result.score == 0.0
    assert "expected" in result.rationale


def test_categorical_accuracy_pass() -> None:
    scorer = CategoricalAccuracyScorer()
    case = _case(expected={"category": "product_defect"})
    result = scorer.score(case, {"category": "product_defect"})
    assert result.score == 1.0
    assert result.dimension == "category_accuracy"


def test_categorical_accuracy_fail() -> None:
    scorer = CategoricalAccuracyScorer()
    case = _case(expected={"category": "product_defect"})
    result = scorer.score(case, {"category": "flaky_test"})
    assert result.score == 0.0


class _Plan(BaseModel):
    title: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)


def test_json_schema_valid_pass() -> None:
    scorer = JsonSchemaValidScorer(schema=_Plan)
    result = scorer.score(_case(), {"title": "Login", "steps": ["a"]})
    assert result.score == 1.0


def test_json_schema_valid_fail_collects_errors() -> None:
    scorer = JsonSchemaValidScorer(schema=_Plan)
    result = scorer.score(_case(), {"title": "", "steps": []})
    assert result.score == 0.0
    assert result.metadata["errors"]


def test_latency_budget_under() -> None:
    scorer = LatencyBudgetScorer(budget_ms=100)
    result = scorer.score(_case(), {"latency_ms": 50})
    assert result.score == 1.0


def test_latency_budget_at_budget_passes() -> None:
    scorer = LatencyBudgetScorer(budget_ms=100)
    result = scorer.score(_case(), {"latency_ms": 100})
    assert result.score == 1.0


def test_latency_budget_falloff_linear() -> None:
    scorer = LatencyBudgetScorer(budget_ms=100)
    # 150ms is 50% over → 0.5 score
    result = scorer.score(_case(), {"latency_ms": 150})
    assert result.score == pytest.approx(0.5, rel=0.01)


def test_latency_budget_clamps_to_zero() -> None:
    scorer = LatencyBudgetScorer(budget_ms=100)
    # 10x budget should clamp to 0.0, not go negative
    result = scorer.score(_case(), {"latency_ms": 1_000})
    assert result.score == 0.0


def test_latency_budget_invalid_input_treated_as_zero() -> None:
    scorer = LatencyBudgetScorer(budget_ms=100)
    result = scorer.score(_case(), {"latency_ms": "not a number"})
    assert result.score == 1.0


def test_latency_budget_rejects_zero() -> None:
    with pytest.raises(ValueError, match="budget_ms"):
        LatencyBudgetScorer(budget_ms=0)


def test_cost_budget_under() -> None:
    scorer = CostBudgetScorer(budget_usd=Decimal("0.10"))
    result = scorer.score(_case(), {"usd_cost": "0.05"})
    assert result.score == 1.0


def test_cost_budget_falloff() -> None:
    scorer = CostBudgetScorer(budget_usd=Decimal("0.10"))
    # 0.15 is 50% over -> 0.5
    result = scorer.score(_case(), {"usd_cost": "0.15"})
    assert result.score == pytest.approx(0.5, rel=0.01)


def test_cost_budget_invalid_input_treated_as_zero() -> None:
    scorer = CostBudgetScorer(budget_usd=Decimal("0.10"))
    result = scorer.score(_case(), {"usd_cost": "garbage"})
    assert result.score == 1.0
