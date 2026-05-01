"""Cost recording + budget enforcement — Story 2.5.

Two cooperating components:

* :class:`DbUsageRecorder` — implements the
  :class:`aqao_agents.llm.recorder.UsageRecorder` Protocol. Buffers
  records during a request and ``flush()``-es them to ``usage_records``
  in a single batch (one INSERT per row, all under the request's
  tenant-scoped session).

* :class:`BudgetEnforcer` — wraps :class:`LLMClient` and tracks running
  USD cost against the workspace policy budget. Pre-flight check
  rejects the call before issuing it; mid-flight kill-switch fires
  when the running total exceeds the budget by > 5% (Story 2.5.1 AC).
"""

from aqao_api.usage.budget import (
    BudgetEnforcer,
    BudgetExceededError,
    EnforcerStats,
)
from aqao_api.usage.recorder import DbUsageRecorder

__all__ = [
    "BudgetEnforcer",
    "BudgetExceededError",
    "DbUsageRecorder",
    "EnforcerStats",
]
