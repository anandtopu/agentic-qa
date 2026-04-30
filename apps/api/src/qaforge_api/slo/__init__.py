"""SLO + error-budget engine — Epic 4.1.

A :class:`Slo` defines an objective (e.g. "99.9% availability over the
last 30 days") plus the metric it measures. :class:`SloCalculator`
consumes :class:`RequestSample` events and produces compliance, an
:class:`ErrorBudget` snapshot, and a :class:`FreezePolicy` decision
when the budget is exhausted.

The package is **transport-agnostic** — production deployments wire a
sample-emitter into the FastAPI middleware (out of scope here) and a
Grafana / Prometheus exporter into the calculator's snapshot. The
in-process types let the freeze policy be tested end-to-end without
either dependency.
"""

from qaforge_api.slo.budget import (
    ErrorBudget,
    FreezeDecision,
    FreezePolicy,
)
from qaforge_api.slo.calculator import SloCalculator, SloSnapshot
from qaforge_api.slo.defaults import DEFAULT_SLOS, slo_by_name
from qaforge_api.slo.types import (
    RequestSample,
    Slo,
    SloKind,
    SloOutcome,
)

__all__ = [
    "DEFAULT_SLOS",
    "ErrorBudget",
    "FreezeDecision",
    "FreezePolicy",
    "RequestSample",
    "Slo",
    "SloCalculator",
    "SloKind",
    "SloOutcome",
    "SloSnapshot",
    "slo_by_name",
]
