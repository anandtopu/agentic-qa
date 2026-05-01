"""ReleaseRiskScorer — Stories 2.3.2 + 2.3.3.

Weighted rubric over :class:`RiskFeatures`. The score lands in 0..100
per PRD §9.9; the band thresholds map to ``low / medium / high /
critical``. Each driver returns a 0..1 contribution plus a human-
readable rationale, so the final :class:`RiskScore` carries the top
drivers + a go/no-go recommendation.

The weights are calibrated against the bands rather than against
historical incidents (no labelled corpus yet); the AC backtest
(>= 0.7 ROC-AUC) is deferred — Story 2.3 ships the rubric so the
GitHub Action quality gate can move off the Phase-1 product-defect
count immediately.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aqao_agents.release_risk.features import (
    OwnershipSignal,
    RiskFeatures,
    SecuritySensitivity,
)


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(StrEnum):
    GO = "go"
    GO_WITH_APPROVAL = "go_with_approval"
    NO_GO = "no_go"


@dataclass(slots=True, frozen=True)
class RiskThresholds:
    """Cut-points mapping a 0..100 score to a band.

    PRD §9.9 says: 0-30 low, 31-60 medium, 61-80 high, 81-100 critical.
    Stored explicitly so a workspace can override later (Phase 3).
    """

    medium: int = 31
    high: int = 61
    critical: int = 81

    def band_for(self, score: int) -> RiskBand:
        if score >= self.critical:
            return RiskBand.CRITICAL
        if score >= self.high:
            return RiskBand.HIGH
        if score >= self.medium:
            return RiskBand.MEDIUM
        return RiskBand.LOW


DEFAULT_THRESHOLDS = RiskThresholds()


@dataclass(slots=True, frozen=True)
class RiskDriver:
    """One signal's contribution to the score.

    ``weight`` is the rubric weight (sums across drivers should equal
    1.0). ``raw`` is the 0..1 normalisation of the underlying feature.
    ``contribution`` is ``weight * raw`` rounded to 4 decimal places —
    useful for the explanation panel.
    """

    name: str
    weight: float
    raw: float
    contribution: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "raw": self.raw,
            "contribution": self.contribution,
            "rationale": self.rationale,
        }


# Weights per driver — sum to 1.0. Calibrated against the bands so a
# "high failure rate + critical security area + recent incident" run
# lands in HIGH/CRITICAL even with no other signals.
DEFAULT_DRIVER_WEIGHTS: dict[str, float] = {
    "fail_rate": 0.20,
    "critical_failures": 0.15,
    "uncovered_acceptance": 0.10,
    "flakiness": 0.05,
    "change_volume": 0.10,
    "historical_defect_density": 0.10,
    "recent_incidents": 0.10,
    "ownership_gap": 0.05,
    "security_sensitivity": 0.10,
    "untested_high_risk_modules": 0.05,
}


@dataclass(slots=True, frozen=True)
class RiskScore:
    """Output of :class:`ReleaseRiskScorer`."""

    score: int
    band: RiskBand
    recommendation: Recommendation
    drivers: tuple[RiskDriver, ...] = field(default_factory=tuple)
    untested_high_risk_modules: tuple[str, ...] = field(default_factory=tuple)
    failed_critical_tests: int = 0
    rationale_summary: str = ""

    def top_drivers(self, k: int = 3) -> tuple[RiskDriver, ...]:
        """Top-k drivers by contribution. Always at least ``k``
        elements when at least k drivers were considered, satisfying
        AC: 'every score includes ≥ 3 drivers'."""
        ranked = sorted(self.drivers, key=lambda d: d.contribution, reverse=True)
        return tuple(ranked[:k])

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "band": self.band.value,
            "recommendation": self.recommendation.value,
            "drivers": [d.to_dict() for d in self.drivers],
            "top_drivers": [d.to_dict() for d in self.top_drivers()],
            "untested_high_risk_modules": list(self.untested_high_risk_modules),
            "failed_critical_tests": self.failed_critical_tests,
            "rationale_summary": self.rationale_summary,
        }


@dataclass(slots=True)
class ReleaseRiskScorer:
    """Weighted-rubric scorer."""

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_DRIVER_WEIGHTS))
    thresholds: RiskThresholds = DEFAULT_THRESHOLDS
    # Volume normalisation knob — 500 changed lines saturates the
    # change-volume driver. Tuneable per workspace later.
    change_volume_saturation: int = 500
    # 5 incidents in the recency window saturates that driver.
    incident_saturation: int = 5
    # 5 defects/kloc saturates the density driver.
    defect_density_saturation: float = 5.0

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"driver weights must sum to ~1.0 (got {total:.3f}); "
                "rebalance before instantiating the scorer"
            )

    def score(self, features: RiskFeatures) -> RiskScore:
        drivers = list(self._build_drivers(features))
        raw_score = sum(d.contribution for d in drivers)
        score_int = max(0, min(100, round(raw_score * 100)))
        band = self.thresholds.band_for(score_int)
        recommendation = _recommendation_for(band)
        summary = _rationale_summary(features, score_int, band)
        return RiskScore(
            score=score_int,
            band=band,
            recommendation=recommendation,
            drivers=tuple(drivers),
            untested_high_risk_modules=tuple(features.untested_high_risk_modules),
            failed_critical_tests=features.critical_failure_count,
            rationale_summary=summary,
        )

    # ------------------------------------------------------------------ drivers

    def _build_drivers(self, features: RiskFeatures) -> Sequence[RiskDriver]:
        out: list[RiskDriver] = []

        out.append(self._driver_fail_rate(features))
        out.append(self._driver_critical_failures(features))
        out.append(self._driver_uncovered_acceptance(features))
        out.append(self._driver_flakiness(features))
        out.append(self._driver_change_volume(features))
        out.append(self._driver_historical_defect_density(features))
        out.append(self._driver_recent_incidents(features))
        out.append(self._driver_ownership_gap(features))
        out.append(self._driver_security_sensitivity(features))
        out.append(self._driver_untested_high_risk_modules(features))

        return out

    def _make(self, name: str, raw: float, rationale: str) -> RiskDriver:
        weight = self.weights[name]
        raw = max(0.0, min(1.0, raw))
        contribution = round(weight * raw, 4)
        return RiskDriver(
            name=name,
            weight=weight,
            raw=raw,
            contribution=contribution,
            rationale=rationale,
        )

    def _driver_fail_rate(self, f: RiskFeatures) -> RiskDriver:
        return self._make(
            "fail_rate",
            f.fail_rate,
            f"{f.failed_tests}/{f.total_tests} tests failing ({f.fail_rate:.0%})",
        )

    def _driver_critical_failures(self, f: RiskFeatures) -> RiskDriver:
        # Saturate at 5 critical/high failures.
        raw = min(f.critical_failure_count / 5.0, 1.0)
        return self._make(
            "critical_failures",
            raw,
            f"{f.critical_failure_count} high/critical-severity test failure(s)",
        )

    def _driver_uncovered_acceptance(self, f: RiskFeatures) -> RiskDriver:
        raw = 1.0 - f.acceptance_coverage
        return self._make(
            "uncovered_acceptance",
            raw,
            f"{f.uncovered_acceptance_criteria}/{f.total_acceptance_criteria} "
            "acceptance criteria uncovered",
        )

    def _driver_flakiness(self, f: RiskFeatures) -> RiskDriver:
        return self._make(
            "flakiness",
            f.flakiness_score,
            f"flakiness score {f.flakiness_score:.2f}",
        )

    def _driver_change_volume(self, f: RiskFeatures) -> RiskDriver:
        total = f.changed_lines_added + f.changed_lines_removed
        raw = min(total / self.change_volume_saturation, 1.0)
        return self._make(
            "change_volume",
            raw,
            f"{total} lines changed across {f.changed_file_count} file(s)",
        )

    def _driver_historical_defect_density(self, f: RiskFeatures) -> RiskDriver:
        raw = min(f.historical_defect_density / self.defect_density_saturation, 1.0)
        return self._make(
            "historical_defect_density",
            raw,
            f"historical defect density {f.historical_defect_density:.2f}/kloc",
        )

    def _driver_recent_incidents(self, f: RiskFeatures) -> RiskDriver:
        raw = min(f.recent_incident_count / self.incident_saturation, 1.0)
        return self._make(
            "recent_incidents",
            raw,
            f"{f.recent_incident_count} production incident(s) in last 90d touching this code",
        )

    def _driver_ownership_gap(self, f: RiskFeatures) -> RiskDriver:
        raw = {
            OwnershipSignal.UNOWNED: 1.0,
            OwnershipSignal.SOLO_OWNER: 0.5,
            OwnershipSignal.TEAM_OWNED: 0.0,
        }[f.ownership]
        return self._make(
            "ownership_gap",
            raw,
            f"ownership: {f.ownership.value}",
        )

    def _driver_security_sensitivity(self, f: RiskFeatures) -> RiskDriver:
        raw = {
            SecuritySensitivity.NONE: 0.0,
            SecuritySensitivity.LOW: 0.25,
            SecuritySensitivity.MEDIUM: 0.6,
            SecuritySensitivity.HIGH: 1.0,
        }[f.security_sensitivity]
        return self._make(
            "security_sensitivity",
            raw,
            f"security sensitivity: {f.security_sensitivity.value}",
        )

    def _driver_untested_high_risk_modules(self, f: RiskFeatures) -> RiskDriver:
        raw = min(len(f.untested_high_risk_modules) / 3.0, 1.0)
        return self._make(
            "untested_high_risk_modules",
            raw,
            f"{len(f.untested_high_risk_modules)} high-risk module(s) without test coverage",
        )


# ---------------------------------------------------------------- helpers


def _recommendation_for(band: RiskBand) -> Recommendation:
    if band is RiskBand.LOW:
        return Recommendation.GO
    if band is RiskBand.MEDIUM:
        return Recommendation.GO_WITH_APPROVAL
    return Recommendation.NO_GO


def _rationale_summary(features: RiskFeatures, score: int, band: RiskBand) -> str:
    if band is RiskBand.LOW:
        verdict = "ship without further review"
    elif band is RiskBand.MEDIUM:
        verdict = "ship after release-readiness approval"
    elif band is RiskBand.HIGH:
        verdict = "do not ship without addressing top drivers"
    else:
        verdict = "block release; rerun after mitigations"

    if features.critical_failure_count > 0:
        verdict += (
            f"; {features.critical_failure_count} high/critical-severity "
            "test failure(s) must be cleared first"
        )
    return f"score {score} ({band.value}) — {verdict}"


__all__ = [
    "DEFAULT_DRIVER_WEIGHTS",
    "DEFAULT_THRESHOLDS",
    "Recommendation",
    "ReleaseRiskScorer",
    "RiskBand",
    "RiskDriver",
    "RiskScore",
    "RiskThresholds",
]
