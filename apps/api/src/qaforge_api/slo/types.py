"""SLO value types — Epic 4.1.

Three SLO kinds cover every PRD §14.5 row:

* :class:`SloKind.AVAILABILITY` — fraction of requests that succeeded
  (status < 5xx). Compliance = success / total.
* :class:`SloKind.LATENCY` — fraction of requests below an explicit
  ``threshold_ms`` (e.g. P95 ≤ 60s expressed as "95% under 60_000ms").
* :class:`SloKind.SUCCESS_RATE` — generic ratio for non-HTTP surfaces
  (eval runs, classifier outputs). Same math as availability with a
  caller-defined "good" boolean.

Every :class:`RequestSample` carries the SLO name it belongs to so a
single :class:`SloCalculator` can score multiple SLOs from one stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class SloKind(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"


class SloOutcome(StrEnum):
    """Verdict for one :class:`RequestSample` against its :class:`Slo`."""

    GOOD = "good"
    BAD = "bad"


@dataclass(slots=True, frozen=True)
class Slo:
    """One target the platform commits to.

    ``objective`` is the fraction of samples that must be ``GOOD``
    over the rolling ``window``. PRD-anchored examples:

    * API availability  ``Slo("api_availability", AVAILABILITY, 0.999)``
    * PR analysis P95   ``Slo("pr_analysis_latency", LATENCY, 0.95,
                              threshold_ms=60_000)``
    * Eval success      ``Slo("eval_success", SUCCESS_RATE, 0.95)``
    """

    name: str
    kind: SloKind
    objective: float
    window: timedelta = timedelta(days=30)
    threshold_ms: int | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not (0.0 < self.objective < 1.0):
            raise ValueError(f"objective must be in (0, 1), got {self.objective}")
        if self.kind is SloKind.LATENCY and self.threshold_ms is None:
            raise ValueError(f"latency SLO {self.name!r} requires threshold_ms")
        if self.kind is not SloKind.LATENCY and self.threshold_ms is not None:
            raise ValueError(f"{self.kind.value} SLO {self.name!r} must not set threshold_ms")


@dataclass(slots=True, frozen=True)
class RequestSample:
    """One observation against an SLO.

    The producer (FastAPI middleware, runner step, eval harness) tags
    every sample with the SLO name, the moment it occurred, and either
    a ``status_code`` (for AVAILABILITY) or a ``latency_ms`` (for
    LATENCY) or an explicit ``success`` flag (for SUCCESS_RATE).
    """

    slo_name: str
    observed_at: datetime
    success: bool | None = None
    status_code: int | None = None
    latency_ms: int | None = None

    def outcome_for(self, slo: Slo) -> SloOutcome:
        if slo.kind is SloKind.AVAILABILITY:
            if self.status_code is None:
                raise ValueError(f"sample for AVAILABILITY SLO {slo.name!r} has no status_code")
            return SloOutcome.GOOD if 100 <= self.status_code < 500 else SloOutcome.BAD
        if slo.kind is SloKind.LATENCY:
            if self.latency_ms is None:
                raise ValueError(f"sample for LATENCY SLO {slo.name!r} has no latency_ms")
            assert slo.threshold_ms is not None
            return SloOutcome.GOOD if self.latency_ms <= slo.threshold_ms else SloOutcome.BAD
        if slo.kind is SloKind.SUCCESS_RATE:
            if self.success is None:
                raise ValueError(f"sample for SUCCESS_RATE SLO {slo.name!r} has no success")
            return SloOutcome.GOOD if self.success else SloOutcome.BAD
        raise ValueError(f"unknown SLO kind: {slo.kind}")  # pragma: no cover


__all__ = ["RequestSample", "Slo", "SloKind", "SloOutcome"]
