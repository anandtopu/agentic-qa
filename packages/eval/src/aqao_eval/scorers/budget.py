"""Budget scorers — latency and USD cost."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from aqao_eval.types import EvalCase, ScoreResult


@dataclass(slots=True)
class LatencyBudgetScorer:
    """Score = 1.0 under budget, linear falloff to 0.0 at 2x budget.

    The output dict is expected to carry ``latency_ms`` (the runner
    populates this from the agent invocation's timing).
    """

    budget_ms: int
    dimension: str = "latency_budget"

    def __post_init__(self) -> None:
        if self.budget_ms <= 0:
            raise ValueError("budget_ms must be > 0")

    def score(self, case: EvalCase, output: dict[str, Any]) -> ScoreResult:
        latency_raw = output.get("latency_ms", 0)
        try:
            latency = int(latency_raw)
        except (TypeError, ValueError):
            latency = 0
        if latency <= self.budget_ms:
            return ScoreResult(
                case_id=case.id,
                dimension=self.dimension,
                score=1.0,
                rationale=f"{latency}ms ≤ {self.budget_ms}ms budget",
            )
        # Linear falloff: 1.0 at budget, 0.0 at 2x budget, clamped.
        over = latency - self.budget_ms
        ratio = max(0.0, 1.0 - (over / self.budget_ms))
        return ScoreResult(
            case_id=case.id,
            dimension=self.dimension,
            score=ratio,
            rationale=(f"{latency}ms is {over}ms over the {self.budget_ms}ms budget"),
        )


@dataclass(slots=True)
class CostBudgetScorer:
    """Score = 1.0 under budget, 0.0 once spend exceeds 2x budget.

    Reads ``output['usd_cost']`` (string Decimal-compatible).
    """

    budget_usd: Decimal
    dimension: str = "cost_budget"

    def __post_init__(self) -> None:
        if self.budget_usd <= 0:
            raise ValueError("budget_usd must be > 0")

    def score(self, case: EvalCase, output: dict[str, Any]) -> ScoreResult:
        raw = output.get("usd_cost", "0")
        try:
            cost = Decimal(str(raw))
        except (TypeError, ValueError, ArithmeticError):
            cost = Decimal("0")

        if cost <= self.budget_usd:
            return ScoreResult(
                case_id=case.id,
                dimension=self.dimension,
                score=1.0,
                rationale=f"${cost} ≤ ${self.budget_usd} budget",
            )
        over = cost - self.budget_usd
        # Use float arithmetic on the falloff — the score is just a
        # ranking, not money math.
        ratio = max(0.0, 1.0 - float(over) / float(self.budget_usd))
        return ScoreResult(
            case_id=case.id,
            dimension=self.dimension,
            score=ratio,
            rationale=f"${cost} is ${over} over the ${self.budget_usd} budget",
        )
