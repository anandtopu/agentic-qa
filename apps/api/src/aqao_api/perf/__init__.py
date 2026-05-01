"""Performance budgets — Epic 4.5.

A :class:`PerfBudget` is a per-capability latency target with a hard
ceiling (the PRD §14.5 number) and an internal warning threshold
(80% of the ceiling, by default). The k6 load tests under
``perf-tests/`` and the in-process timing decorators consume the same
budget definitions so a regression surfaces in both surfaces.
"""

from aqao_api.perf.budgets import (
    DEFAULT_PERF_BUDGETS,
    PerfBudget,
    PerfBudgetReport,
    evaluate_perf_run,
    perf_budget_by_name,
)
from aqao_api.perf.timing import TimedCall, time_call

__all__ = [
    "DEFAULT_PERF_BUDGETS",
    "PerfBudget",
    "PerfBudgetReport",
    "TimedCall",
    "evaluate_perf_run",
    "perf_budget_by_name",
    "time_call",
]
