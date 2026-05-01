"""SloCalculator + snapshot — Epic 4.1.

The calculator is intentionally **stateless across runs**: callers
hand it a sample stream and it returns a :class:`SloSnapshot` with
the windowed compliance + the resulting :class:`ErrorBudget`. A
production deployment can persist the SLO definitions in DB +
periodically replay recent samples; this module doesn't take a
position on that.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aqao_api.slo.budget import ErrorBudget
from aqao_api.slo.types import RequestSample, Slo, SloOutcome


@dataclass(slots=True, frozen=True)
class SloSnapshot:
    """Per-SLO rollup at a point in time."""

    slo: Slo
    window_start: datetime
    window_end: datetime
    total_samples: int
    good_samples: int
    bad_samples: int
    compliance: float
    error_budget: ErrorBudget

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo": {
                "name": self.slo.name,
                "kind": self.slo.kind.value,
                "objective": self.slo.objective,
                "window_days": int(self.slo.window.total_seconds() // 86400),
                "threshold_ms": self.slo.threshold_ms,
            },
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_samples": self.total_samples,
            "good_samples": self.good_samples,
            "bad_samples": self.bad_samples,
            "compliance": self.compliance,
            "error_budget": self.error_budget.to_dict(),
        }


@dataclass(slots=True)
class SloCalculator:
    """Compute :class:`SloSnapshot` rollups for a set of SLOs."""

    slos: Mapping[str, Slo] = field(default_factory=dict)

    def evaluate(
        self,
        samples: Iterable[RequestSample],
        *,
        now: datetime | None = None,
    ) -> dict[str, SloSnapshot]:
        moment = now or datetime.now(UTC)
        sample_list = list(samples)
        out: dict[str, SloSnapshot] = {}
        for name, slo in self.slos.items():
            out[name] = self._evaluate_one(slo=slo, samples=sample_list, now=moment)
        return out

    # ------------------------------------------------------------ helpers

    def _evaluate_one(
        self,
        *,
        slo: Slo,
        samples: list[RequestSample],
        now: datetime,
    ) -> SloSnapshot:
        cutoff = now - slo.window
        scoped = [s for s in samples if s.slo_name == slo.name and s.observed_at >= cutoff]
        good = sum(1 for s in scoped if s.outcome_for(slo) is SloOutcome.GOOD)
        bad = len(scoped) - good
        compliance = (good / len(scoped)) if scoped else 1.0
        budget = ErrorBudget.from_compliance(slo=slo, compliance=compliance)
        return SloSnapshot(
            slo=slo,
            window_start=cutoff,
            window_end=now,
            total_samples=len(scoped),
            good_samples=good,
            bad_samples=bad,
            compliance=compliance,
            error_budget=budget,
        )


__all__ = ["SloCalculator", "SloSnapshot"]
