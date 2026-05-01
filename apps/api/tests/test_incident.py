"""Incident routing + paging tests — Epic 4.2.

Covers:

* Severity matrix integrity (every Severity has a rule; targets are
  monotonic SEV1 < SEV2 < SEV3 < SEV4).
* :class:`Alert` carries a runbook path for every :class:`AlertKind`.
* :class:`IncidentRouter` infers the right severity per alert kind +
  honours tag overrides.
* :class:`LogPageNotifier` emits at the right log level for the
  severity (ERROR for SEV1/SEV2, WARNING for SEV3/SEV4) and reports
  the channels it would deliver to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import structlog

from aqao_api.incident import (
    DEFAULT_SEVERITY_MATRIX,
    Alert,
    AlertKind,
    IncidentRouter,
    LogPageNotifier,
    Severity,
)
from aqao_api.incident.alert import RUNBOOK_INDEX


def _alert(kind: AlertKind, **kwargs: object) -> Alert:
    base: dict[str, object] = {
        "kind": kind,
        "summary": "test alert",
        "fired_at": datetime(2026, 5, 1, tzinfo=UTC),
    }
    base.update(kwargs)
    return Alert(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- matrix


def test_every_severity_has_a_rule() -> None:
    missing = [s for s in Severity if s not in DEFAULT_SEVERITY_MATRIX]
    assert not missing, missing


def test_severity_targets_are_monotonic() -> None:
    """Higher severity = tighter targets. A regression that flips
    these would silently downgrade pages."""
    rules = [DEFAULT_SEVERITY_MATRIX[s] for s in Severity]
    response_times = [r.response_time_target for r in rules]
    mttrs = [r.mttr_target for r in rules]
    assert response_times == sorted(response_times)
    assert mttrs == sorted(mttrs)


def test_sev1_and_sev2_require_postmortem() -> None:
    assert DEFAULT_SEVERITY_MATRIX[Severity.SEV1].postmortem_required
    assert DEFAULT_SEVERITY_MATRIX[Severity.SEV2].postmortem_required
    assert not DEFAULT_SEVERITY_MATRIX[Severity.SEV3].postmortem_required
    assert not DEFAULT_SEVERITY_MATRIX[Severity.SEV4].postmortem_required


def test_sev1_pages_three_channels() -> None:
    rule = DEFAULT_SEVERITY_MATRIX[Severity.SEV1]
    assert "page" in rule.page_channels
    assert "slack-incident" in rule.page_channels
    assert "email" in rule.page_channels


# ---------------------------------------------------------------- alerts


def test_every_alert_kind_has_a_runbook_path() -> None:
    missing = [k for k in AlertKind if k not in RUNBOOK_INDEX]
    assert not missing, missing


def test_alert_runbook_path_round_trips() -> None:
    alert = _alert(AlertKind.SLO_BURN)
    assert alert.runbook_path.endswith("slo-burn.md")
    assert "kind" in alert.to_dict()


# ---------------------------------------------------------------- router


def test_audit_tampered_routes_to_sev1_always() -> None:
    decision = IncidentRouter().route(_alert(AlertKind.AUDIT_TAMPERED))
    assert decision.severity is Severity.SEV1


def test_slo_burn_on_availability_is_sev1_others_sev2() -> None:
    router = IncidentRouter()
    avail = router.route(_alert(AlertKind.SLO_BURN, tags={"slo_name": "api_availability"}))
    latency = router.route(_alert(AlertKind.SLO_BURN, tags={"slo_name": "pr_analysis_latency"}))
    assert avail.severity is Severity.SEV1
    assert latency.severity is Severity.SEV2


def test_dlq_depth_escalates_at_threshold() -> None:
    router = IncidentRouter(dlq_critical_depth=500)
    low = router.route(_alert(AlertKind.DLQ_DEPTH, tags={"depth": "100"}))
    high = router.route(_alert(AlertKind.DLQ_DEPTH, tags={"depth": "750"}))
    assert low.severity is Severity.SEV3
    assert high.severity is Severity.SEV2


def test_provider_budget_exhausted_is_sev2() -> None:
    decision = IncidentRouter().route(_alert(AlertKind.PROVIDER_BUDGET_EXHAUSTED))
    assert decision.severity is Severity.SEV2


def test_eval_regression_is_sev3() -> None:
    decision = IncidentRouter().route(_alert(AlertKind.EVAL_REGRESSION))
    assert decision.severity is Severity.SEV3


def test_approval_overdue_and_external_tracker_down_are_sev4() -> None:
    router = IncidentRouter()
    assert router.route(_alert(AlertKind.APPROVAL_OVERDUE)).severity is Severity.SEV4
    assert router.route(_alert(AlertKind.EXTERNAL_TRACKER_DOWN)).severity is Severity.SEV4


def test_provider_decision_overdue_is_sev4() -> None:
    """Story 6.2 / TD-008: a stalled go/no-go is a process miss, not an
    outage — files a ticket via SEV4 like the other queue-piling-up
    alerts. The bridge service in `services.lifecycle_alerts` only
    fires this kind when `breach_count > 0`."""
    decision = IncidentRouter().route(_alert(AlertKind.PROVIDER_DECISION_OVERDUE))
    assert decision.severity is Severity.SEV4
    assert decision.alert.runbook_path.endswith("provider-decision-overdue.md")


def test_tag_severity_override_is_honoured() -> None:
    """A tag-driven manual escalation forces severity even when the
    inferred level would be lower — supports the "this is actually
    bigger than it looks" workflow."""
    router = IncidentRouter()
    decision = router.route(
        _alert(
            AlertKind.APPROVAL_OVERDUE,
            tags={"severity": "SEV1"},
        )
    )
    assert decision.severity is Severity.SEV1


def test_tag_severity_override_rejects_unknown_value() -> None:
    router = IncidentRouter()
    with pytest.raises(ValueError, match="unknown severity"):
        router.route(_alert(AlertKind.SLO_BURN, tags={"severity": "SEV9"}))


# ---------------------------------------------------------------- notifier


def test_log_notifier_uses_error_level_for_sev1_sev2() -> None:
    """Severity dictates log level so a log-only deployment can route
    on level alone while real PagerDuty is in flight."""
    router = IncidentRouter()
    notifier = LogPageNotifier()
    with structlog.testing.capture_logs() as captured:
        notifier.page(router.route(_alert(AlertKind.AUDIT_TAMPERED)))
    assert captured[0]["log_level"] == "error"


def test_log_notifier_uses_warning_level_for_sev3_sev4() -> None:
    router = IncidentRouter()
    notifier = LogPageNotifier()
    with structlog.testing.capture_logs() as captured:
        notifier.page(router.route(_alert(AlertKind.APPROVAL_OVERDUE)))
    assert captured[0]["log_level"] == "warning"


def test_log_notifier_returns_decision_with_delivered_channels() -> None:
    router = IncidentRouter()
    notifier = LogPageNotifier()
    decision = notifier.page(router.route(_alert(AlertKind.AUDIT_TAMPERED)))
    assert "page" in decision.delivered_to
    assert decision.transport == "structured-log"


# ---------------------------------------------------------------- mock drill


def test_mock_drill_sev1_meets_response_target() -> None:
    """Story 4.2 AC: mock incident drill resolves within target MTTR.
    The drill is a simulation — we verify the *targets* are
    achievable on paper, not a real wall-clock run."""
    router = IncidentRouter()
    decision = router.route(_alert(AlertKind.AUDIT_TAMPERED))
    # Simulate: page acknowledged in 4 minutes, mitigated in 45 minutes.
    ack_in = timedelta(minutes=4)
    mttr_actual = timedelta(minutes=45)
    assert ack_in <= decision.rule.response_time_target
    assert mttr_actual <= decision.rule.mttr_target
    assert decision.rule.postmortem_required
