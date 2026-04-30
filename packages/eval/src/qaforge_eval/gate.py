"""Baseline gating — Story 2.6.3.

Compare a fresh :class:`Scorecard` to a pinned baseline. Each dimension
has a tolerance (default 0.0 — any drop is a regression). Returns a
structured report; the CLI converts a non-empty regression list into a
non-zero exit code so CI blocks the merge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from qaforge_eval.types import DimensionAggregate, Scorecard

DEFAULT_REGRESSION_TOLERANCE = 0.0
"""Default per-dimension tolerance — any drop counts as a regression."""


@dataclass(slots=True)
class RegressionFinding:
    dimension: str
    baseline_value: float
    branch_value: float
    delta: float
    metric: str  # "mean" | "pass_rate"
    tolerance: float

    @property
    def is_regression(self) -> bool:
        return self.delta < -self.tolerance


@dataclass(slots=True)
class GateReport:
    findings: list[RegressionFinding] = field(default_factory=list)
    new_dimensions: list[str] = field(default_factory=list)
    missing_dimensions: list[str] = field(default_factory=list)

    @property
    def regressions(self) -> list[RegressionFinding]:
        return [f for f in self.findings if f.is_regression]

    @property
    def has_regressions(self) -> bool:
        return any(f.is_regression for f in self.findings)

    def summary_lines(self) -> list[str]:
        out: list[str] = []
        if self.regressions:
            out.append(f"{len(self.regressions)} regression(s) detected:")
            for f in self.regressions:
                out.append(
                    f"  - {f.dimension}.{f.metric}: "
                    f"baseline={f.baseline_value:.3f} branch={f.branch_value:.3f} "
                    f"delta={f.delta:+.3f} (tolerance {f.tolerance:.3f})"
                )
        else:
            out.append("No regressions detected.")
        if self.new_dimensions:
            out.append(f"New dimensions on branch: {', '.join(self.new_dimensions)}")
        if self.missing_dimensions:
            out.append(
                f"Dimensions missing on branch (present in baseline): "
                f"{', '.join(self.missing_dimensions)}"
            )
        return out


@dataclass(slots=True)
class BaselineGate:
    tolerance: float = DEFAULT_REGRESSION_TOLERANCE
    per_dimension_tolerance: dict[str, float] = field(default_factory=dict)

    def compare(self, *, baseline: Scorecard, branch: Scorecard) -> GateReport:
        baseline_by_dim = {d.dimension: d for d in baseline.dimensions}
        branch_by_dim = {d.dimension: d for d in branch.dimensions}

        report = GateReport(
            new_dimensions=sorted(set(branch_by_dim) - set(baseline_by_dim)),
            missing_dimensions=sorted(set(baseline_by_dim) - set(branch_by_dim)),
        )

        for dimension, base_dim in baseline_by_dim.items():
            branch_dim = branch_by_dim.get(dimension)
            if branch_dim is None:
                continue
            tol = self.per_dimension_tolerance.get(dimension, self.tolerance)
            report.findings.append(_finding(dimension, base_dim, branch_dim, "mean", tol))
            report.findings.append(_finding(dimension, base_dim, branch_dim, "pass_rate", tol))
        return report

    @staticmethod
    def load_baseline(path: Path) -> Scorecard:
        return Scorecard.model_validate_json(path.read_text("utf-8"))

    @staticmethod
    def write_baseline(path: Path, scorecard: Scorecard) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(scorecard.to_json(), encoding="utf-8")

    @staticmethod
    def load_optional(path: Path) -> Scorecard | None:
        if not path.is_file():
            return None
        try:
            return BaselineGate.load_baseline(path)
        except (json.JSONDecodeError, ValueError):
            return None


def _finding(
    dimension: str,
    base: DimensionAggregate,
    branch: DimensionAggregate,
    metric: str,
    tolerance: float,
) -> RegressionFinding:
    base_val = getattr(base, metric)
    branch_val = getattr(branch, metric)
    return RegressionFinding(
        dimension=dimension,
        baseline_value=base_val,
        branch_value=branch_val,
        delta=branch_val - base_val,
        metric=metric,
        tolerance=tolerance,
    )
