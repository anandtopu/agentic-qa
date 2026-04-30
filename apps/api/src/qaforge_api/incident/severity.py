"""Severity matrix — Epic 4.2.

Four severities cover everything QAForge can throw at on-call:

* **SEV1** — production outage / data loss / security incident.
  Page immediately, all hands, MTTR target 1 hour.
* **SEV2** — major degradation (one tenant down, integration broken).
  Page primary on-call, MTTR target 4 hours.
* **SEV3** — minor degradation (slow but functional, partial feature
  outage). Email + Slack, MTTR target 1 business day.
* **SEV4** — cosmetic / informational. File a ticket, fix during
  normal work.

Per the Phase-4 AC (mock incident drill resolves within target MTTR
+ post-mortem within 5 business days), the matrix is the contract
the on-call workflow validates against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum


class Severity(StrEnum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


@dataclass(slots=True, frozen=True)
class SeverityRule:
    severity: Severity
    response_time_target: timedelta
    mttr_target: timedelta
    postmortem_required: bool
    page_channels: tuple[str, ...]
    description: str


DEFAULT_SEVERITY_MATRIX: dict[Severity, SeverityRule] = {
    Severity.SEV1: SeverityRule(
        severity=Severity.SEV1,
        response_time_target=timedelta(minutes=5),
        mttr_target=timedelta(hours=1),
        postmortem_required=True,
        page_channels=("page", "slack-incident", "email"),
        description=(
            "Production outage, data loss, or active security incident. "
            "All hands; CEO + CTO notified within 15 minutes."
        ),
    ),
    Severity.SEV2: SeverityRule(
        severity=Severity.SEV2,
        response_time_target=timedelta(minutes=15),
        mttr_target=timedelta(hours=4),
        postmortem_required=True,
        page_channels=("page", "slack-incident"),
        description=(
            "Major degradation — one tenant fully impacted or a core "
            "integration broken. On-call primary engaged."
        ),
    ),
    Severity.SEV3: SeverityRule(
        severity=Severity.SEV3,
        response_time_target=timedelta(hours=1),
        mttr_target=timedelta(days=1),
        postmortem_required=False,
        page_channels=("slack-eng", "email"),
        description=(
            "Minor degradation — slow but functional, partial feature "
            "outage. No page; emailed to the on-call team."
        ),
    ),
    Severity.SEV4: SeverityRule(
        severity=Severity.SEV4,
        response_time_target=timedelta(days=1),
        mttr_target=timedelta(days=5),
        postmortem_required=False,
        page_channels=("ticket",),
        description="Cosmetic or informational. File a ticket; no page.",
    ),
}


def severity_rule(severity: Severity) -> SeverityRule:
    return DEFAULT_SEVERITY_MATRIX[severity]


__all__ = ["DEFAULT_SEVERITY_MATRIX", "Severity", "SeverityRule", "severity_rule"]
