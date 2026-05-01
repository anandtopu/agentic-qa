"""IncidentRouter — Epic 4.2.

Maps an :class:`Alert` to a :class:`Severity` based on the alert
kind + tag matching. The routing rules are explicit and opinionated:

* ``audit_tampered`` is always SEV1 (security incident).
* ``slo_burn`` is SEV1 if the burned SLO is ``api_availability``,
  SEV2 otherwise (latency burns are degraded-mode, not outage).
* ``llm_provider_down`` is SEV2 — the platform has provider fallback
  + circuit breakers (Epic 4.3) so it's not an immediate outage.
* ``dlq_depth`` is SEV3 unless the depth exceeds the
  ``dlq_critical_depth`` tag, in which case SEV2.
* ``provider_budget_exhausted`` is SEV2 — runs blocked but no data
  loss.
* ``eval_regression`` is SEV3.
* ``approval_overdue`` and ``external_tracker_down`` are SEV4 — file
  a ticket.

Tag-based overrides let one alert kind escalate without rewriting
the routing logic — e.g. an `slo_burn` alert tagged with
``critical=true`` can be forced to SEV1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aqao_api.incident.alert import Alert, AlertKind
from aqao_api.incident.severity import (
    DEFAULT_SEVERITY_MATRIX,
    Severity,
    SeverityRule,
)


@dataclass(slots=True, frozen=True)
class RoutingDecision:
    alert: Alert
    severity: Severity
    rule: SeverityRule

    def to_dict(self) -> dict[str, object]:
        return {
            "alert": self.alert.to_dict(),
            "severity": self.severity.value,
            "page_channels": list(self.rule.page_channels),
            "response_time_target_seconds": int(self.rule.response_time_target.total_seconds()),
            "mttr_target_seconds": int(self.rule.mttr_target.total_seconds()),
            "postmortem_required": self.rule.postmortem_required,
        }


@dataclass(slots=True)
class IncidentRouter:
    """Decide a severity for each alert."""

    matrix: dict[Severity, SeverityRule] = field(
        default_factory=lambda: dict(DEFAULT_SEVERITY_MATRIX)
    )
    dlq_critical_depth: int = 1_000

    def route(self, alert: Alert) -> RoutingDecision:
        # Caller-forced SEV via tags wins — supports manual escalation.
        forced = alert.tags.get("severity")
        if forced is not None:
            try:
                return self._decide(alert, Severity(forced.upper()))
            except ValueError as exc:
                raise ValueError(
                    f"alert {alert.kind.value!r} requested unknown severity {forced!r}"
                ) from exc

        sev = self._infer(alert)
        return self._decide(alert, sev)

    # ------------------------------------------------------------ rules

    def _infer(self, alert: Alert) -> Severity:
        if alert.kind is AlertKind.AUDIT_TAMPERED:
            return Severity.SEV1
        if alert.kind is AlertKind.SLO_BURN:
            slo_name = alert.tags.get("slo_name", "")
            return Severity.SEV1 if slo_name == "api_availability" else Severity.SEV2
        if alert.kind is AlertKind.LLM_PROVIDER_DOWN:
            return Severity.SEV2
        if alert.kind is AlertKind.DLQ_DEPTH:
            depth = self._parse_dlq_depth(alert)
            return Severity.SEV2 if depth >= self.dlq_critical_depth else Severity.SEV3
        if alert.kind is AlertKind.PROVIDER_BUDGET_EXHAUSTED:
            return Severity.SEV2
        if alert.kind is AlertKind.EVAL_REGRESSION:
            return Severity.SEV3
        if alert.kind in {
            AlertKind.APPROVAL_OVERDUE,
            AlertKind.EXTERNAL_TRACKER_DOWN,
            AlertKind.PROVIDER_DECISION_OVERDUE,
        }:
            return Severity.SEV4
        return Severity.SEV3  # safe default — a missed alert should still rouse someone

    def _decide(self, alert: Alert, severity: Severity) -> RoutingDecision:
        rule = self.matrix[severity]
        return RoutingDecision(alert=alert, severity=severity, rule=rule)

    @staticmethod
    def _parse_dlq_depth(alert: Alert) -> int:
        raw_depth = alert.tags.get("depth", "0")
        try:
            depth = int(raw_depth)
        except ValueError as exc:
            raise ValueError(
                f"alert {alert.kind.value!r} has invalid DLQ depth {raw_depth!r}"
            ) from exc
        if depth < 0:
            raise ValueError(f"alert {alert.kind.value!r} has negative DLQ depth {depth!r}")
        return depth


__all__ = ["IncidentRouter", "RoutingDecision"]
