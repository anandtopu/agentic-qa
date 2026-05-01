"""Unit tests for the heuristic pre-classifier — Story 1.7.1."""

from __future__ import annotations

from decimal import Decimal

from aqao_agents.classifier import FailureCategory, FailureSignal
from aqao_agents.classifier.heuristic import HeuristicClassifier


def _signal(**kwargs: object) -> FailureSignal:
    base: dict[str, object] = {
        "signal_id": kwargs.pop("signal_id", "sig-1"),
    }
    base.update(kwargs)
    return FailureSignal.model_validate(base)


def test_classifies_http_5xx_as_product_defect() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(http_status_code=503, error_message="upstream"))
    assert match is not None
    assert match.category is FailureCategory.PRODUCT_DEFECT
    assert match.rule == "http_5xx"


def test_classifies_401_as_environment_issue() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(http_status_code=401))
    assert match is not None
    assert match.category is FailureCategory.ENVIRONMENT_ISSUE
    assert match.confidence >= Decimal("0.80")


def test_classifies_408_as_environment_issue() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(http_status_code=408))
    assert match is not None
    assert match.rule == "http_timeout_status"


def test_classifies_etimedout_as_environment_issue() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="ETIMEDOUT during request to staging.example"))
    assert match is not None
    assert match.category is FailureCategory.ENVIRONMENT_ISSUE
    assert match.rule == "network_timeout"


def test_classifies_dns_failure() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="getaddrinfo ENOTFOUND staging"))
    assert match is not None
    assert match.rule == "dns_resolution"


def test_classifies_browser_nav_error() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="net::ERR_CERT_AUTHORITY_INVALID"))
    assert match is not None
    assert match.rule == "browser_nav_error"


def test_classifies_selector_not_found_as_test_issue() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="Selector resolved to 0 elements: 'button.submit'"))
    assert match is not None
    assert match.category is FailureCategory.TEST_ISSUE
    assert match.rule == "selector_not_found"


def test_classifies_assertion_failure_as_product_defect() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="AssertionError: 200 != 201"))
    assert match is not None
    assert match.category is FailureCategory.PRODUCT_DEFECT


def test_classifies_python_traceback_as_unknown() -> None:
    h = HeuristicClassifier()
    match = h.classify(
        _signal(stderr_excerpt='Traceback (most recent call last):\n  File "x.py"...')
    )
    assert match is not None
    assert match.category is FailureCategory.UNKNOWN


def test_classifies_429_rate_limit() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="Got 429 Too Many Requests"))
    assert match is not None
    assert match.rule == "rate_limited"


def test_classifies_missing_fixture_as_data_issue() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="fixture 'baseline_users' not found"))
    assert match is not None
    assert match.category is FailureCategory.DATA_ISSUE


def test_signal_with_no_recognised_pattern_returns_none() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message="something completely unexpected happened"))
    assert match is None


def test_signal_with_empty_text_and_no_status_returns_none() -> None:
    h = HeuristicClassifier()
    match = h.classify(_signal(error_message=""))
    assert match is None


def test_classify_to_classification_wraps_match() -> None:
    h = HeuristicClassifier()
    classification = h.classify_to_classification(_signal(http_status_code=502))
    assert classification is not None
    assert classification.category is FailureCategory.PRODUCT_DEFECT
    assert classification.classified_by.value == "heuristic"
    assert classification.signal_id == "sig-1"
