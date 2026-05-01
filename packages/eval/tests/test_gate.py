"""Unit tests for the BaselineGate — Story 2.6.3.

The AC requires a deliberate prompt regression to be caught and
blocked. We model that as a baseline scorecard with a high pass-rate
and a branch scorecard whose pass-rate dropped — the gate must surface
that as a regression.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aqao_eval import (
    BaselineGate,
    DimensionAggregate,
    Scorecard,
)

_PIN = datetime(2026, 5, 1, tzinfo=UTC)


def _scorecard(*dims: tuple[str, float, float]) -> Scorecard:
    """Build a Scorecard from ``(dimension, mean, pass_rate)`` triples."""
    return Scorecard(
        agent_name="planner",
        dataset_name="example",
        dataset_version="v1",
        started_at=_PIN,
        finished_at=_PIN,
        total_cases=10,
        total_usd_cost=Decimal("0"),
        total_latency_ms=0,
        dimensions=[
            DimensionAggregate(
                dimension=name,
                cases=10,
                mean=mean,
                p50=mean,
                pass_rate=pass_rate,
            )
            for name, mean, pass_rate in dims
        ],
        cases=[],
    )


def test_no_regression_when_branch_matches_baseline() -> None:
    baseline = _scorecard(("exact_match:answer", 1.0, 1.0))
    branch = _scorecard(("exact_match:answer", 1.0, 1.0))
    report = BaselineGate().compare(baseline=baseline, branch=branch)
    assert not report.has_regressions


def test_regression_caught_when_pass_rate_drops() -> None:
    baseline = _scorecard(("exact_match:answer", 1.0, 1.0))
    branch = _scorecard(("exact_match:answer", 0.7, 0.7))
    report = BaselineGate().compare(baseline=baseline, branch=branch)
    assert report.has_regressions
    deltas = {(f.metric, f.delta < 0) for f in report.regressions}
    assert ("pass_rate", True) in deltas
    assert ("mean", True) in deltas


def test_per_dimension_tolerance_allows_small_drop() -> None:
    baseline = _scorecard(("category_accuracy", 0.80, 0.80))
    branch = _scorecard(("category_accuracy", 0.78, 0.78))
    gate = BaselineGate(per_dimension_tolerance={"category_accuracy": 0.05})
    report = gate.compare(baseline=baseline, branch=branch)
    assert not report.has_regressions


def test_global_tolerance_allows_uniform_noise() -> None:
    baseline = _scorecard(("a", 0.90, 0.90), ("b", 0.85, 0.85))
    branch = _scorecard(("a", 0.88, 0.88), ("b", 0.83, 0.83))
    gate = BaselineGate(tolerance=0.05)
    report = gate.compare(baseline=baseline, branch=branch)
    assert not report.has_regressions


def test_new_dimension_on_branch_is_reported() -> None:
    baseline = _scorecard(("a", 1.0, 1.0))
    branch = _scorecard(("a", 1.0, 1.0), ("b", 1.0, 1.0))
    report = BaselineGate().compare(baseline=baseline, branch=branch)
    assert report.new_dimensions == ["b"]


def test_missing_dimension_on_branch_is_reported() -> None:
    baseline = _scorecard(("a", 1.0, 1.0), ("b", 1.0, 1.0))
    branch = _scorecard(("a", 1.0, 1.0))
    report = BaselineGate().compare(baseline=baseline, branch=branch)
    assert report.missing_dimensions == ["b"]


def test_summary_lines_describe_regressions_concretely() -> None:
    baseline = _scorecard(("a", 1.0, 1.0))
    branch = _scorecard(("a", 0.4, 0.4))
    report = BaselineGate().compare(baseline=baseline, branch=branch)
    text = "\n".join(report.summary_lines())
    assert "regression" in text.lower()
    assert "a.mean" in text
    assert "a.pass_rate" in text


def test_baseline_round_trip_to_disk(tmp_path: Path) -> None:
    card = _scorecard(("a", 1.0, 1.0))
    path = tmp_path / "nested" / "baseline.json"
    BaselineGate.write_baseline(path, card)
    loaded = BaselineGate.load_baseline(path)
    assert loaded.dimensions[0].dimension == "a"


def test_load_optional_returns_none_on_missing(tmp_path: Path) -> None:
    assert BaselineGate.load_optional(tmp_path / "missing.json") is None


def test_load_optional_returns_none_on_garbled_file(tmp_path: Path) -> None:
    path = tmp_path / "garbage.json"
    path.write_text("not json", encoding="utf-8")
    assert BaselineGate.load_optional(path) is None
