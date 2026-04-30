"""Alert types + runbook index — Epic 4.2.

An :class:`Alert` is the structured form of any signal that may
require human attention: SLO breach, reliability circuit-break, eval
regression, security event. The router (next module) maps an alert
to a :class:`Severity` and the freeze policy (Epic 4.1) consumes the
result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AlertKind(StrEnum):
    """Source of the alert. Drives the severity-routing rules."""

    SLO_BURN = "slo_burn"  # Epic 4.1 freeze policy fired
    LLM_PROVIDER_DOWN = "llm_provider_down"  # Epic 4.3 circuit broke
    DLQ_DEPTH = "dlq_depth"  # Epic 4.3 dead-letter accumulating
    EVAL_REGRESSION = "eval_regression"  # Epic 3.5 nightly alert
    AUDIT_TAMPERED = "audit_tampered"  # Story 2.4.1 signature mismatch
    APPROVAL_OVERDUE = "approval_overdue"  # Epic 2.1 expired approvals piling up
    EXTERNAL_TRACKER_DOWN = "external_tracker_down"  # Epic 3.2 webhook flooding errors
    PROVIDER_BUDGET_EXHAUSTED = "provider_budget_exhausted"  # Epic 2.5 budget enforcer kill-switch


# Each alert kind carries an opinion about the runbook a human should
# open first. The runbook index lives under docs/runbooks/ — Story
# 4.2 ships the index entries; per-alert runbook bodies are filled in
# as the alerts themselves prove out under real load.
RUNBOOK_INDEX: dict[AlertKind, str] = {
    AlertKind.SLO_BURN: "docs/runbooks/slo-burn.md",
    AlertKind.LLM_PROVIDER_DOWN: "docs/runbooks/llm-provider-down.md",
    AlertKind.DLQ_DEPTH: "docs/runbooks/dlq-depth.md",
    AlertKind.EVAL_REGRESSION: "docs/runbooks/eval-regression.md",
    AlertKind.AUDIT_TAMPERED: "docs/runbooks/audit-tampered.md",
    AlertKind.APPROVAL_OVERDUE: "docs/runbooks/approval-overdue.md",
    AlertKind.EXTERNAL_TRACKER_DOWN: "docs/runbooks/external-tracker-down.md",
    AlertKind.PROVIDER_BUDGET_EXHAUSTED: "docs/runbooks/provider-budget-exhausted.md",
}


@dataclass(slots=True, frozen=True)
class Alert:
    """One structured alert event."""

    kind: AlertKind
    summary: str
    fired_at: datetime
    detail: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def runbook_path(self) -> str:
        return RUNBOOK_INDEX[self.kind]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "summary": self.summary,
            "fired_at": self.fired_at.isoformat(),
            "detail": self.detail,
            "tags": dict(self.tags),
            "runbook": self.runbook_path,
            "extra": dict(self.extra),
        }


__all__ = ["RUNBOOK_INDEX", "Alert", "AlertKind"]
