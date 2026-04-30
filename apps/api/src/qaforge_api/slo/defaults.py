"""Default SLOs for QAForge — Epic 4.1.

Anchored to PRD §14.5 capability targets + §14.1 reliability
expectations:

* API availability    — 99.9% over 30 days.
* PR analysis         — 95% under 60s (PRD: "PR analysis < 60s").
* Test plan gen       — 95% under 90s.
* API smoke           — 95% under 180s (3 minutes).
* UI smoke            — 95% under 600s (10 minutes).
* Failure classify    — 95% under 60s.
* Evidence report     — 95% under 30s.
* Eval success rate   — 95% successful runs over 7 days (Phase-3 nightly).

Workspaces can override these per environment; the defaults are what
the platform ships with.
"""

from __future__ import annotations

from datetime import timedelta

from qaforge_api.slo.types import Slo, SloKind

DEFAULT_SLOS: tuple[Slo, ...] = (
    Slo(
        name="api_availability",
        kind=SloKind.AVAILABILITY,
        objective=0.999,
        window=timedelta(days=30),
        description="API responses with status < 500 over 30d.",
    ),
    Slo(
        name="pr_analysis_latency",
        kind=SloKind.LATENCY,
        objective=0.95,
        window=timedelta(days=30),
        threshold_ms=60_000,
        description="PR analysis end-to-end ≤ 60s, p95.",
    ),
    Slo(
        name="test_plan_generation_latency",
        kind=SloKind.LATENCY,
        objective=0.95,
        window=timedelta(days=30),
        threshold_ms=90_000,
        description="Test plan generation ≤ 90s, p95.",
    ),
    Slo(
        name="api_smoke_latency",
        kind=SloKind.LATENCY,
        objective=0.95,
        window=timedelta(days=30),
        threshold_ms=180_000,
        description="API smoke run ≤ 3 min, p95.",
    ),
    Slo(
        name="ui_smoke_latency",
        kind=SloKind.LATENCY,
        objective=0.95,
        window=timedelta(days=30),
        threshold_ms=600_000,
        description="UI smoke run ≤ 10 min, p95.",
    ),
    Slo(
        name="failure_classification_latency",
        kind=SloKind.LATENCY,
        objective=0.95,
        window=timedelta(days=30),
        threshold_ms=60_000,
        description="Failure classification ≤ 60s, p95.",
    ),
    Slo(
        name="evidence_report_latency",
        kind=SloKind.LATENCY,
        objective=0.95,
        window=timedelta(days=30),
        threshold_ms=30_000,
        description="Evidence report rendering ≤ 30s, p95.",
    ),
    Slo(
        name="eval_success_rate",
        kind=SloKind.SUCCESS_RATE,
        objective=0.95,
        window=timedelta(days=7),
        description="Nightly eval runs that complete without errors.",
    ),
)


def slo_by_name(name: str) -> Slo:
    for slo in DEFAULT_SLOS:
        if slo.name == name:
            return slo
    raise KeyError(f"no default SLO named {name!r}")


__all__ = ["DEFAULT_SLOS", "slo_by_name"]
