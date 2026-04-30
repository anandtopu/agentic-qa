"""Incident management — Epic 4.2.

* :class:`Severity` — SEV1 (catastrophic) → SEV4 (cosmetic). Each
  level carries a :attr:`response_time_target` and an
  :attr:`mttr_target` so the on-call workflow can flag overruns.
* :class:`Alert` — one structured event from the SLO engine,
  reliability layer, or external monitor.
* :class:`PageNotifier` Protocol — anything that can fan an alert
  out to the rotation. :class:`LogPageNotifier` is the default
  transport; PagerDuty / Opsgenie drop in later by satisfying the
  same Protocol.
* :class:`IncidentRouter` — maps an :class:`Alert` to a
  :class:`PageDecision` based on severity + alert kind.
"""

from qaforge_api.incident.alert import Alert, AlertKind
from qaforge_api.incident.notifier import (
    LogPageNotifier,
    PageDecision,
    PageNotifier,
)
from qaforge_api.incident.router import IncidentRouter
from qaforge_api.incident.severity import (
    DEFAULT_SEVERITY_MATRIX,
    Severity,
    SeverityRule,
)

__all__ = [
    "DEFAULT_SEVERITY_MATRIX",
    "Alert",
    "AlertKind",
    "IncidentRouter",
    "LogPageNotifier",
    "PageDecision",
    "PageNotifier",
    "Severity",
    "SeverityRule",
]
