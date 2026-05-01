"""Flakiness-aware classifier tests — Story 3.3.2.

The AC asks for a measurable drop in the false-positive defect rate
(target < 15% per PRD §19). We verify by:

1. The unit-level rule-overrides: a high-flakiness signal converts a
   would-be ``PRODUCT_DEFECT`` to ``FLAKY_TEST``, and a no-rule-match
   signal becomes ``FLAKY_TEST`` outright.
2. A synthetic dataset where every PRODUCT_DEFECT classification is a
   false positive (the test was actually flaky). With the flakiness
   feature wired in, the FP rate drops below the 15% target.
"""

from __future__ import annotations

from dataclasses import dataclass

from aqao_agents.classifier import FailureCategory, FailureSignal
from aqao_agents.classifier.heuristic import (
    FLAKINESS_FLIP_THRESHOLD,
    HeuristicClassifier,
)


def _signal(
    *,
    flakiness_score: float | None = None,
    http_status_code: int | None = None,
    error_message: str = "",
    test_name: str = "test_thing",
) -> FailureSignal:
    return FailureSignal(
        signal_id="sig-1",
        test_name=test_name,
        error_message=error_message,
        http_status_code=http_status_code,
        flakiness_score=flakiness_score,
    )


# ---------------------------------------------------------------- unit


def test_below_threshold_does_not_change_classification() -> None:
    """A 5xx with low flakiness stays a PRODUCT_DEFECT."""
    classifier = HeuristicClassifier()
    signal = _signal(http_status_code=500, flakiness_score=0.10)
    match = classifier.classify(signal)
    assert match is not None
    assert match.category is FailureCategory.PRODUCT_DEFECT
    assert match.rule == "http_5xx"


def test_at_or_above_threshold_overrides_product_defect_to_flaky() -> None:
    """Same 5xx but with high flip-rate -> classifier downgrades to FLAKY_TEST.

    This is the false-positive reduction the AC asks for.
    """
    classifier = HeuristicClassifier()
    signal = _signal(http_status_code=500, flakiness_score=0.40)
    match = classifier.classify(signal)
    assert match is not None
    assert match.category is FailureCategory.FLAKY_TEST
    assert "flakiness_override" in match.rule


def test_no_rule_match_with_flakiness_classifies_as_flaky() -> None:
    """A signal nothing else matches plus a high flip-rate is FLAKY_TEST,
    not UNKNOWN — keeps the classifier from punting on something we
    actually have evidence for."""
    classifier = HeuristicClassifier()
    signal = _signal(error_message="something weird happened", flakiness_score=0.50)
    match = classifier.classify(signal)
    assert match is not None
    assert match.category is FailureCategory.FLAKY_TEST
    assert match.rule == "flakiness_observed"


def test_environment_issue_is_not_overridden_by_flakiness() -> None:
    """A 401 from auth misconfig is genuinely environmental — the
    classifier must not relabel it as a flaky test."""
    classifier = HeuristicClassifier()
    signal = _signal(http_status_code=401, flakiness_score=0.80)
    match = classifier.classify(signal)
    assert match is not None
    assert match.category is FailureCategory.ENVIRONMENT_ISSUE


def test_threshold_default_matches_constant() -> None:
    classifier = HeuristicClassifier()
    assert classifier.flakiness_threshold == FLAKINESS_FLIP_THRESHOLD


# ---------------------------------------------------------------- AC: FP rate drop


@dataclass(slots=True, frozen=True)
class _LabelledSignal:
    """A test signal with the ground-truth label we know it should
    have. Used to compute false-positive rates against the classifier."""

    signal: FailureSignal
    true_category: FailureCategory


def _build_synthetic_dataset() -> list[_LabelledSignal]:
    """30 signals, mix of true product defects and flaky tests that
    *look* like product defects (5xx) but are actually non-deterministic."""
    out: list[_LabelledSignal] = []
    # 10 genuine product defects — low flakiness, 5xx response.
    for i in range(10):
        out.append(
            _LabelledSignal(
                signal=FailureSignal(
                    signal_id=f"defect-{i}",
                    test_name=f"test_real_bug_{i}",
                    error_message="AssertionError: expected 200 got 500",
                    http_status_code=500,
                    flakiness_score=0.05,  # stable test
                ),
                true_category=FailureCategory.PRODUCT_DEFECT,
            )
        )
    # 20 flaky tests masquerading as product defects — same surface
    # error (5xx) but the test has been flapping.
    for i in range(20):
        out.append(
            _LabelledSignal(
                signal=FailureSignal(
                    signal_id=f"flake-{i}",
                    test_name=f"test_flake_{i}",
                    error_message="AssertionError: expected 200 got 500",
                    http_status_code=500,
                    flakiness_score=0.5,  # half of recent runs flipped
                ),
                true_category=FailureCategory.FLAKY_TEST,
            )
        )
    return out


def test_false_positive_rate_drops_below_15_percent_with_flakiness() -> None:
    """AC: false-positive defect rate target < 15% per PRD §19.

    A "false positive" here = a flaky test that the classifier
    mislabels as PRODUCT_DEFECT. With the flakiness feature off
    (signals stripped to flakiness_score=None) the synthetic set
    produces a high FP rate; turning the feature on drops it below
    the 15% target.
    """
    classifier = HeuristicClassifier()
    dataset = _build_synthetic_dataset()

    flakes = [s for s in dataset if s.true_category is FailureCategory.FLAKY_TEST]

    # --- Without flakiness feature: baseline ---
    fp_without = sum(
        1
        for s in flakes
        if (
            classifier.classify(s.signal.model_copy(update={"flakiness_score": None}))
            or _no_match()
        ).category
        is FailureCategory.PRODUCT_DEFECT
    )
    fp_rate_without = fp_without / len(flakes)

    # --- With flakiness feature: post-fix ---
    fp_with = sum(
        1
        for s in flakes
        if (classifier.classify(s.signal) or _no_match()).category is FailureCategory.PRODUCT_DEFECT
    )
    fp_rate_with = fp_with / len(flakes)

    # Sanity: baseline FP rate is high (>= 50% of flakes mislabelled
    # as product defects when the classifier doesn't see flakiness).
    assert fp_rate_without >= 0.50, fp_rate_without
    # AC: with the feature wired, FP rate is below 15%.
    assert fp_rate_with < 0.15, fp_rate_with
    # And the drop is meaningful — > 35 percentage points.
    assert fp_rate_without - fp_rate_with > 0.35


class _NoMatch:
    """Sentinel for signals the classifier punts on — keeps the
    list-comprehension above readable."""

    category = FailureCategory.UNKNOWN


def _no_match() -> _NoMatch:
    return _NoMatch()
