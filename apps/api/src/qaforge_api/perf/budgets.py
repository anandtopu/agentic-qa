"""PerfBudget + budget evaluation — Epic 4.5.

The budgets here mirror the latency SLOs from Epic 4.1's defaults.
PRD §14.5 numbers are the ceilings; ``warn_pct`` (default 80%) sets
the soft threshold for ``WARN``. A run is ``PASS`` if every recorded
sample lands under the warn threshold; ``WARN`` if any sample is
between warn and ceiling; ``FAIL`` if any sample exceeds the ceiling.

The :func:`evaluate_perf_run` consumer is dataset-shaped — the k6
load test exports a JSON of ``{name: [latency_ms,...]}`` and this
module produces a :class:`PerfBudgetReport` from it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class BudgetVerdict(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(slots=True, frozen=True)
class PerfBudget:
    """One latency budget anchored to PRD §14.5."""

    name: str
    ceiling_ms: int
    warn_pct: float = 0.80
    description: str = ""

    def __post_init__(self) -> None:
        if self.ceiling_ms <= 0:
            raise ValueError("ceiling_ms must be > 0")
        if not (0.0 < self.warn_pct < 1.0):
            raise ValueError("warn_pct must be in (0, 1)")

    @property
    def warn_threshold_ms(self) -> int:
        return int(self.ceiling_ms * self.warn_pct)


DEFAULT_PERF_BUDGETS: tuple[PerfBudget, ...] = (
    PerfBudget(
        name="pr_analysis",
        ceiling_ms=60_000,
        description="PR diff -> plan -> first run started, end-to-end.",
    ),
    PerfBudget(
        name="test_plan_generation",
        ceiling_ms=90_000,
        description="Planner agent produces a TestPlan from one requirement.",
    ),
    PerfBudget(
        name="api_smoke",
        ceiling_ms=180_000,
        description="API smoke run (Newman/pytest).",
    ),
    PerfBudget(
        name="ui_smoke",
        ceiling_ms=600_000,
        description="UI smoke run (Playwright).",
    ),
    PerfBudget(
        name="failure_classification",
        ceiling_ms=60_000,
        description="Heuristic + LLM classifier round-trip.",
    ),
    PerfBudget(
        name="evidence_report",
        ceiling_ms=30_000,
        description="Markdown report rendering + storage upload.",
    ),
)


def perf_budget_by_name(name: str) -> PerfBudget:
    for b in DEFAULT_PERF_BUDGETS:
        if b.name == name:
            return b
    raise KeyError(f"no default perf budget named {name!r}")


@dataclass(slots=True, frozen=True)
class CapabilityResult:
    """Per-capability rollup of one perf run."""

    budget: PerfBudget
    sample_count: int
    p50_ms: int
    p95_ms: int
    p99_ms: int
    max_ms: int
    verdict: BudgetVerdict

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.budget.name,
            "ceiling_ms": self.budget.ceiling_ms,
            "warn_threshold_ms": self.budget.warn_threshold_ms,
            "samples": self.sample_count,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "max_ms": self.max_ms,
            "verdict": self.verdict.value,
        }


@dataclass(slots=True, frozen=True)
class PerfBudgetReport:
    """Roll-up across every capability evaluated."""

    capabilities: tuple[CapabilityResult, ...] = field(default_factory=tuple)

    @property
    def overall_verdict(self) -> BudgetVerdict:
        # Hierarchy: any FAIL -> FAIL; else any WARN -> WARN; else PASS.
        verdicts = {c.verdict for c in self.capabilities}
        if BudgetVerdict.FAIL in verdicts:
            return BudgetVerdict.FAIL
        if BudgetVerdict.WARN in verdicts:
            return BudgetVerdict.WARN
        return BudgetVerdict.PASS

    @property
    def has_failures(self) -> bool:
        return self.overall_verdict is BudgetVerdict.FAIL

    def to_dict(self) -> dict[str, object]:
        return {
            "overall_verdict": self.overall_verdict.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
        }


def _percentile(samples: Sequence[int], p: float) -> int:
    """Discrete-rank percentile over an already-sorted ``samples``
    list. Returns 0 for an empty input so an empty capability is a
    PASS (caller is responsible for noticing the zero sample count
    if they care)."""
    if not samples:
        return 0
    rank = max(0, min(len(samples) - 1, round(p * (len(samples) - 1))))
    return samples[rank]


def evaluate_perf_run(
    samples_by_capability: Mapping[str, Sequence[int]],
    *,
    budgets: Sequence[PerfBudget] = DEFAULT_PERF_BUDGETS,
) -> PerfBudgetReport:
    """Compute a :class:`PerfBudgetReport` from a dict of latencies
    keyed by capability name."""
    results: list[CapabilityResult] = []
    by_name = {b.name: b for b in budgets}
    for name, raw in samples_by_capability.items():
        if name not in by_name:
            continue
        budget = by_name[name]
        sorted_samples = sorted(raw)
        p50 = _percentile(sorted_samples, 0.50)
        p95 = _percentile(sorted_samples, 0.95)
        p99 = _percentile(sorted_samples, 0.99)
        worst = max(sorted_samples) if sorted_samples else 0
        verdict = _verdict_for(budget=budget, samples=sorted_samples)
        results.append(
            CapabilityResult(
                budget=budget,
                sample_count=len(sorted_samples),
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                max_ms=worst,
                verdict=verdict,
            )
        )
    return PerfBudgetReport(capabilities=tuple(results))


def _verdict_for(*, budget: PerfBudget, samples: Sequence[int]) -> BudgetVerdict:
    if not samples:
        return BudgetVerdict.PASS
    if any(s > budget.ceiling_ms for s in samples):
        return BudgetVerdict.FAIL
    if any(s > budget.warn_threshold_ms for s in samples):
        return BudgetVerdict.WARN
    return BudgetVerdict.PASS


__all__ = [
    "DEFAULT_PERF_BUDGETS",
    "BudgetVerdict",
    "CapabilityResult",
    "PerfBudget",
    "PerfBudgetReport",
    "evaluate_perf_run",
    "perf_budget_by_name",
]
