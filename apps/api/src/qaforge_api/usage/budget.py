"""Per-run budget enforcement — Story 2.5.1.

The :class:`BudgetEnforcer` accumulates the USD cost of every LLM call
issued through it and compares the running total against the workspace
policy's ``max_cost_usd_per_run``. Per the AC, runs are allowed up to
**5% above** the configured budget (acknowledging the kill switch fires
*after* a call returns, never mid-token).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from qaforge_agents.llm.client import LLMClient
from qaforge_agents.llm.types import LLMRequest, LLMResponse

DEFAULT_SLACK = Decimal("1.05")  # AC: ≤ 5% over the configured cap


class BudgetExceededError(RuntimeError):
    """Raised on the call that would push the running total past the budget."""

    def __init__(
        self,
        *,
        running_total: Decimal,
        budget: Decimal,
        request_estimate: Decimal,
    ) -> None:
        super().__init__(
            f"budget exceeded: running={running_total} + estimate={request_estimate} "
            f"> budget={budget} * slack"
        )
        self.running_total = running_total
        self.budget = budget
        self.request_estimate = request_estimate


@dataclass(slots=True)
class EnforcerStats:
    calls_made: int = 0
    calls_blocked: int = 0
    running_total: Decimal = Decimal("0")
    budget: Decimal = Decimal("0")
    slack: Decimal = DEFAULT_SLACK


@dataclass(slots=True)
class BudgetEnforcer:
    """Wraps :class:`LLMClient` with per-run budget tracking.

    Construct one per workflow run — the running total is instance-scoped.
    """

    client: LLMClient
    budget_usd: Decimal
    slack: Decimal = DEFAULT_SLACK
    stats: EnforcerStats = field(default_factory=EnforcerStats)

    def __post_init__(self) -> None:
        if self.budget_usd <= 0:
            raise ValueError("budget_usd must be > 0")
        if self.slack < Decimal("1"):
            raise ValueError("slack must be >= 1.0 (no slack = 1.0)")
        self.stats.budget = self.budget_usd
        self.stats.slack = self.slack

    @property
    def effective_cap(self) -> Decimal:
        return (self.budget_usd * self.slack).quantize(Decimal("0.000001"))

    def remaining(self) -> Decimal:
        return self.effective_cap - self.stats.running_total

    async def complete(
        self,
        request: LLMRequest,
        *,
        request_estimate_usd: Decimal | None = None,
    ) -> LLMResponse:
        """Pre-flight check, dispatch, and update running total.

        ``request_estimate_usd`` is an optional hint — if the caller
        knows the request will cost roughly N USD, the enforcer can
        reject before the call even hits the wire. When omitted the
        enforcer falls back to mid-flight checking only.
        """
        running = self.stats.running_total
        cap = self.effective_cap

        if request_estimate_usd is not None and running + request_estimate_usd > cap:
            self.stats.calls_blocked += 1
            raise BudgetExceededError(
                running_total=running,
                budget=self.budget_usd,
                request_estimate=request_estimate_usd,
            )

        response = await self.client.complete(request)
        cost = response.usage.usd_cost
        self.stats.running_total = running + cost
        self.stats.calls_made += 1

        if self.stats.running_total > cap:
            # Mid-flight kill switch: the call we just made tipped us
            # over. Surface as BudgetExceeded so the orchestrator can
            # mark the workflow ``failed`` rather than continue burning
            # cost.
            raise BudgetExceededError(
                running_total=self.stats.running_total,
                budget=self.budget_usd,
                request_estimate=cost,
            )

        return response
