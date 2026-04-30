"""SLO + error-budget tests — Epic 4.1.

Covers:

* :class:`Slo` validation rejects bad shapes (objective out of range,
  latency without threshold, non-latency with threshold).
* Per-sample :meth:`RequestSample.outcome_for` math for all three
  kinds.
* :class:`SloCalculator` windows samples + computes compliance.
* :class:`ErrorBudget.from_compliance` math at boundaries.
* :class:`FreezePolicy` escalates through NORMAL → WATCH →
  SOFT_FREEZE → HARD_FREEZE in lock-step with budget exhaustion.
* Default SLOs from PRD §14.5 are well-formed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from qaforge_api.slo import (
    DEFAULT_SLOS,
    ErrorBudget,
    FreezeDecision,
    FreezePolicy,
    RequestSample,
    Slo,
    SloCalculator,
    SloKind,
    SloOutcome,
    slo_by_name,
)
from qaforge_api.slo.budget import FreezeLevel

# ---------------------------------------------------------------- Slo


def test_slo_rejects_objective_outside_open_interval() -> None:
    with pytest.raises(ValueError, match="objective"):
        Slo(name="x", kind=SloKind.AVAILABILITY, objective=1.0)
    with pytest.raises(ValueError, match="objective"):
        Slo(name="x", kind=SloKind.AVAILABILITY, objective=0.0)


def test_latency_slo_requires_threshold_ms() -> None:
    with pytest.raises(ValueError, match="threshold_ms"):
        Slo(name="x", kind=SloKind.LATENCY, objective=0.95)


def test_non_latency_slo_rejects_threshold_ms() -> None:
    with pytest.raises(ValueError, match="must not set threshold_ms"):
        Slo(
            name="x",
            kind=SloKind.AVAILABILITY,
            objective=0.95,
            threshold_ms=100,
        )


# ---------------------------------------------------------------- RequestSample


def test_availability_sample_classifies_4xx_as_good() -> None:
    """4xx is 'we served the request' — outside SLO scope. Only 5xx
    counts as a bad sample for availability."""
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.999)
    sample = RequestSample(
        slo_name="api",
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
        status_code=404,
    )
    assert sample.outcome_for(slo) is SloOutcome.GOOD


def test_availability_sample_classifies_5xx_as_bad() -> None:
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.999)
    sample = RequestSample(
        slo_name="api",
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
        status_code=503,
    )
    assert sample.outcome_for(slo) is SloOutcome.BAD


def test_latency_sample_at_threshold_is_good() -> None:
    slo = Slo(
        name="pr",
        kind=SloKind.LATENCY,
        objective=0.95,
        threshold_ms=60_000,
    )
    sample = RequestSample(
        slo_name="pr",
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
        latency_ms=60_000,
    )
    assert sample.outcome_for(slo) is SloOutcome.GOOD
    over = RequestSample(
        slo_name="pr",
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
        latency_ms=60_001,
    )
    assert over.outcome_for(slo) is SloOutcome.BAD


def test_success_rate_sample_uses_explicit_flag() -> None:
    slo = Slo(name="eval", kind=SloKind.SUCCESS_RATE, objective=0.95)
    good = RequestSample(
        slo_name="eval",
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
        success=True,
    )
    bad = RequestSample(
        slo_name="eval",
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
        success=False,
    )
    assert good.outcome_for(slo) is SloOutcome.GOOD
    assert bad.outcome_for(slo) is SloOutcome.BAD


def test_sample_missing_required_field_raises() -> None:
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.999)
    sample = RequestSample(slo_name="api", observed_at=datetime(2026, 5, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="status_code"):
        sample.outcome_for(slo)


# ---------------------------------------------------------------- calculator


def test_calculator_returns_perfect_compliance_for_no_samples() -> None:
    """A fresh deployment has no samples — compliance defaults to 1.0
    so the budget shows full and the freeze policy stays NORMAL."""
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.999)
    calc = SloCalculator(slos={"api": slo})
    snap = calc.evaluate([])["api"]
    assert snap.total_samples == 0
    assert snap.compliance == 1.0
    assert snap.error_budget.remaining_fraction == 1.0


def test_calculator_windows_samples_correctly() -> None:
    slo = Slo(
        name="api",
        kind=SloKind.AVAILABILITY,
        objective=0.999,
        window=timedelta(days=7),
    )
    calc = SloCalculator(slos={"api": slo})
    now = datetime(2026, 5, 1, tzinfo=UTC)
    samples = [
        # In window: 9 good + 1 bad -> 90% compliance.
        RequestSample(
            slo_name="api",
            observed_at=now - timedelta(days=1),
            status_code=200,
        ),
        *[
            RequestSample(
                slo_name="api",
                observed_at=now - timedelta(hours=i),
                status_code=200,
            )
            for i in range(8)
        ],
        RequestSample(
            slo_name="api",
            observed_at=now - timedelta(hours=10),
            status_code=503,
        ),
        # Out of window: should be filtered.
        RequestSample(
            slo_name="api",
            observed_at=now - timedelta(days=10),
            status_code=503,
        ),
    ]
    snap = calc.evaluate(samples, now=now)["api"]
    assert snap.total_samples == 10
    assert snap.bad_samples == 1
    assert snap.compliance == 0.9


def test_calculator_separates_samples_by_slo_name() -> None:
    slo_a = Slo(name="a", kind=SloKind.AVAILABILITY, objective=0.999)
    slo_b = Slo(name="b", kind=SloKind.AVAILABILITY, objective=0.999)
    calc = SloCalculator(slos={"a": slo_a, "b": slo_b})
    now = datetime(2026, 5, 1, tzinfo=UTC)
    samples = [
        RequestSample(slo_name="a", observed_at=now, status_code=200),
        RequestSample(slo_name="b", observed_at=now, status_code=503),
    ]
    snaps = calc.evaluate(samples, now=now)
    assert snaps["a"].compliance == 1.0
    assert snaps["b"].compliance == 0.0


# ---------------------------------------------------------------- error budget


def test_error_budget_full_at_perfect_compliance() -> None:
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.999)
    budget = ErrorBudget.from_compliance(slo=slo, compliance=1.0)
    assert budget.consumed_fraction == 0.0
    assert budget.remaining_fraction == 1.0
    assert not budget.exhausted


def test_error_budget_exhausted_at_objective_floor() -> None:
    """Objective 0.999 -> allowed_bad = 0.001. 0.999 compliance burns
    the budget exactly. Anything below exhausts it."""
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.999)
    budget = ErrorBudget.from_compliance(slo=slo, compliance=0.999)
    assert pytest.approx(budget.consumed_fraction) == 1.0
    assert budget.exhausted


def test_error_budget_partial_burn_is_proportional() -> None:
    slo = Slo(name="api", kind=SloKind.AVAILABILITY, objective=0.99)
    # allowed_bad = 0.01; observed_bad = 0.005 -> 50% consumed.
    budget = ErrorBudget.from_compliance(slo=slo, compliance=0.995)
    assert pytest.approx(budget.consumed_fraction) == 0.5
    assert pytest.approx(budget.remaining_fraction) == 0.5


# ---------------------------------------------------------------- freeze policy


def test_freeze_policy_escalates_with_budget_exhaustion() -> None:
    policy = FreezePolicy()  # default thresholds
    slo_name = "api"

    healthy = ErrorBudget(
        slo_name=slo_name,
        allowed_bad_fraction=0.001,
        consumed_fraction=0.10,
        remaining_fraction=0.90,
    )
    watch = ErrorBudget(
        slo_name=slo_name,
        allowed_bad_fraction=0.001,
        consumed_fraction=0.60,
        remaining_fraction=0.40,
    )
    soft = ErrorBudget(
        slo_name=slo_name,
        allowed_bad_fraction=0.001,
        consumed_fraction=0.85,
        remaining_fraction=0.15,
    )
    hard = ErrorBudget(
        slo_name=slo_name,
        allowed_bad_fraction=0.001,
        consumed_fraction=1.0,
        remaining_fraction=0.0,
    )

    assert policy.decide(healthy).level is FreezeLevel.NORMAL
    assert policy.decide(watch).level is FreezeLevel.WATCH
    assert policy.decide(soft).level is FreezeLevel.SOFT_FREEZE
    assert policy.decide(hard).level is FreezeLevel.HARD_FREEZE


def test_freeze_decision_carries_human_readable_reason() -> None:
    policy = FreezePolicy()
    decision = policy.decide(
        ErrorBudget(
            slo_name="api",
            allowed_bad_fraction=0.001,
            consumed_fraction=1.0,
            remaining_fraction=0.0,
        )
    )
    assert isinstance(decision, FreezeDecision)
    assert "exhausted" in decision.reason


def test_freeze_policy_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError, match="freeze < warn"):
        FreezePolicy(warn_threshold=0.20, freeze_threshold=0.50)


# ---------------------------------------------------------------- defaults


def test_default_slos_cover_every_prd_capability() -> None:
    names = {slo.name for slo in DEFAULT_SLOS}
    expected = {
        "api_availability",
        "pr_analysis_latency",
        "test_plan_generation_latency",
        "api_smoke_latency",
        "ui_smoke_latency",
        "failure_classification_latency",
        "evidence_report_latency",
        "eval_success_rate",
    }
    missing = expected - names
    assert not missing, missing


def test_default_pr_analysis_target_matches_prd_60s() -> None:
    slo = slo_by_name("pr_analysis_latency")
    assert slo.threshold_ms == 60_000
    assert slo.objective == 0.95


def test_slo_by_name_unknown_raises() -> None:
    with pytest.raises(KeyError):
        slo_by_name("nope")


# ---------------------------------------------------------------- end-to-end


def test_calculator_to_freeze_decision_round_trip() -> None:
    """End-to-end: feed samples → calculator → budget → freeze policy."""
    slo = Slo(
        name="api",
        kind=SloKind.AVAILABILITY,
        objective=0.99,
        window=timedelta(days=1),
    )
    calc = SloCalculator(slos={"api": slo})
    now = datetime(2026, 5, 1, tzinfo=UTC)
    # 100 samples, 5 bad -> compliance 0.95 -> well below 0.99 ->
    # budget exhausted -> hard freeze.
    samples = [
        RequestSample(slo_name="api", observed_at=now, status_code=200) for _ in range(95)
    ] + [RequestSample(slo_name="api", observed_at=now, status_code=503) for _ in range(5)]
    snap = calc.evaluate(samples, now=now)["api"]
    decision = FreezePolicy().decide(snap.error_budget)
    assert decision.level is FreezeLevel.HARD_FREEZE
