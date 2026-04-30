"""Unit tests for the Release Risk Scoring agent — Epic 2.3."""

from __future__ import annotations

import pytest

from qaforge_agents.release_risk import (
    DEFAULT_DRIVER_WEIGHTS,
    OwnershipSignal,
    Recommendation,
    ReleaseRiskScorer,
    RiskBand,
    RiskFeatures,
    RiskThresholds,
    SecuritySensitivity,
    TestSeverity,
)


def _features(**overrides: object) -> RiskFeatures:
    base: dict[str, object] = {
        "total_tests": 100,
        "passed_tests": 100,
        "failed_tests": 0,
        "changed_file_count": 1,
        "changed_lines_added": 10,
        "changed_lines_removed": 0,
    }
    base.update(overrides)
    return RiskFeatures.model_validate(base)


# ---------------------------------------------------------------- features


def test_features_reject_overcounted_tests() -> None:
    with pytest.raises(ValueError, match="passed \\+ failed"):
        RiskFeatures(
            total_tests=10,
            passed_tests=8,
            failed_tests=5,
            changed_file_count=1,
        )


def test_features_reject_overcounted_acceptance() -> None:
    with pytest.raises(ValueError, match="acceptance"):
        RiskFeatures(
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            changed_file_count=0,
            uncovered_acceptance_criteria=5,
            total_acceptance_criteria=3,
        )


def test_features_fail_rate_zero_when_no_tests() -> None:
    f = RiskFeatures(
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        changed_file_count=0,
    )
    assert f.fail_rate == 0.0
    assert f.acceptance_coverage == 1.0


def test_features_critical_failure_count_only_counts_high_and_critical() -> None:
    f = _features(
        total_tests=10,
        passed_tests=6,
        failed_tests=4,
        failed_test_severities=[
            TestSeverity.LOW,
            TestSeverity.MEDIUM,
            TestSeverity.HIGH,
            TestSeverity.CRITICAL,
        ],
    )
    assert f.critical_failure_count == 2


# ---------------------------------------------------------------- scorer


def test_scorer_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="weights must sum"):
        ReleaseRiskScorer(weights={"fail_rate": 0.5, "flakiness": 0.2})


def test_clean_run_lands_in_low_band() -> None:
    """A clean run (no failures, small change, no risk indicators)
    should be Low risk and recommend Go."""
    score = ReleaseRiskScorer().score(_features())
    assert score.band is RiskBand.LOW
    assert score.recommendation is Recommendation.GO
    assert score.score < 31


def test_high_failure_run_lands_above_low() -> None:
    f = _features(
        total_tests=20,
        passed_tests=2,
        failed_tests=18,
        failed_test_severities=[TestSeverity.HIGH] * 5,
    )
    score = ReleaseRiskScorer().score(f)
    assert score.band is not RiskBand.LOW
    assert score.recommendation is not Recommendation.GO


def test_score_includes_at_least_three_drivers() -> None:
    """AC: every score includes ≥ 3 drivers."""
    score = ReleaseRiskScorer().score(_features())
    assert len(score.drivers) >= 3
    top3 = score.top_drivers(3)
    assert len(top3) == 3


def test_top_drivers_are_ranked_by_contribution() -> None:
    f = _features(
        total_tests=10,
        passed_tests=5,
        failed_tests=5,
        failed_test_severities=[TestSeverity.CRITICAL] * 3,
        security_sensitivity=SecuritySensitivity.HIGH,
        recent_incident_count=3,
    )
    score = ReleaseRiskScorer().score(f)
    top = score.top_drivers(3)
    contributions = [d.contribution for d in top]
    assert contributions == sorted(contributions, reverse=True)


def test_recommendation_for_each_band() -> None:
    scorer = ReleaseRiskScorer()
    low = scorer.score(_features())
    medium = scorer.score(
        _features(
            total_tests=20,
            passed_tests=14,
            failed_tests=6,
            failed_test_severities=[TestSeverity.HIGH, TestSeverity.HIGH],
            uncovered_acceptance_criteria=4,
            total_acceptance_criteria=10,
            recent_incident_count=2,
            security_sensitivity=SecuritySensitivity.MEDIUM,
            flakiness_score=0.3,
            historical_defect_density=2.0,
        )
    )
    critical = scorer.score(
        _features(
            total_tests=10,
            passed_tests=0,
            failed_tests=10,
            failed_test_severities=[TestSeverity.CRITICAL] * 5,
            security_sensitivity=SecuritySensitivity.HIGH,
            recent_incident_count=5,
            ownership=OwnershipSignal.UNOWNED,
            historical_defect_density=5.0,
            untested_high_risk_modules=["auth", "billing", "tokens"],
            uncovered_acceptance_criteria=10,
            total_acceptance_criteria=10,
            flakiness_score=1.0,
            changed_lines_added=500,
        )
    )
    assert low.recommendation is Recommendation.GO
    assert medium.recommendation in {
        Recommendation.GO_WITH_APPROVAL,
        Recommendation.NO_GO,
    }
    assert critical.recommendation is Recommendation.NO_GO


def test_thresholds_match_prd_bands() -> None:
    """PRD §9.9: 0-30 low, 31-60 medium, 61-80 high, 81-100 critical."""
    t = RiskThresholds()
    assert t.band_for(0) is RiskBand.LOW
    assert t.band_for(30) is RiskBand.LOW
    assert t.band_for(31) is RiskBand.MEDIUM
    assert t.band_for(60) is RiskBand.MEDIUM
    assert t.band_for(61) is RiskBand.HIGH
    assert t.band_for(80) is RiskBand.HIGH
    assert t.band_for(81) is RiskBand.CRITICAL
    assert t.band_for(100) is RiskBand.CRITICAL


def test_score_is_clamped_to_0_100() -> None:
    """Even a maximally adversarial input must not produce > 100 or < 0."""
    f = _features(
        total_tests=10,
        passed_tests=0,
        failed_tests=10,
        failed_test_severities=[TestSeverity.CRITICAL] * 10,
        security_sensitivity=SecuritySensitivity.HIGH,
        recent_incident_count=100,
        ownership=OwnershipSignal.UNOWNED,
        historical_defect_density=1_000.0,
        untested_high_risk_modules=["a", "b", "c", "d"],
        uncovered_acceptance_criteria=10,
        total_acceptance_criteria=10,
        flakiness_score=1.0,
        changed_lines_added=10_000,
        changed_lines_removed=10_000,
    )
    score = ReleaseRiskScorer().score(f)
    assert 0 <= score.score <= 100


def test_score_to_dict_round_trips_drivers_and_recommendation() -> None:
    score = ReleaseRiskScorer().score(_features())
    d = score.to_dict()
    assert d["band"] == score.band.value
    assert d["recommendation"] == score.recommendation.value
    assert len(d["drivers"]) == len(DEFAULT_DRIVER_WEIGHTS)
    assert len(d["top_drivers"]) == 3


def test_rationale_summary_calls_out_critical_failures() -> None:
    f = _features(
        total_tests=10,
        passed_tests=8,
        failed_tests=2,
        failed_test_severities=[TestSeverity.CRITICAL, TestSeverity.HIGH],
    )
    score = ReleaseRiskScorer().score(f)
    assert "critical-severity" in score.rationale_summary


def test_untested_high_risk_modules_propagate_into_score() -> None:
    f = _features(
        untested_high_risk_modules=["auth", "billing"],
    )
    score = ReleaseRiskScorer().score(f)
    assert score.untested_high_risk_modules == ("auth", "billing")
