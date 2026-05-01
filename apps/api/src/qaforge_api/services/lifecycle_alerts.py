"""ModelLifecycleAlertService — TD-008 / Epic 6.2.

Bridges :class:`ModelLifecycleService.awaiting_decision` to the
Phase-4 incident router so a stalled go/no-go decision actually
pages someone instead of sitting silently in the API response.

The service is invoked on a cadence (k8s CronJob, Lambda, or any
external scheduler hitting the route) — same pattern as the
retention sweep and approval-expiry jobs. When the bridge sees one
or more candidates whose age has crossed the configurable SLA, it
fires a :class:`PROVIDER_DECISION_OVERDUE` alert and lets the
existing router + page-notifier chain decide where it goes.

If no candidates have breached the SLA, no alert is emitted — the
service is the bridge, not a heartbeat.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from qaforge_api.incident import (
    Alert,
    AlertKind,
    IncidentRouter,
    PageDecision,
    PageNotifier,
)
from qaforge_api.services.model_lifecycle import (
    DEFAULT_DECISION_SLA,
    AwaitingDecisionRow,
    ModelLifecycleService,
)


@dataclass(slots=True, frozen=True)
class OverdueCheckReport:
    """What the bridge saw and what it did about it.

    ``page_decision`` is ``None`` when no SLA breach is detected —
    the cadence ran but had nothing to escalate. ``breached`` carries
    the rows that drove the alert so callers can log or surface them
    without re-querying.
    """

    checked_at: datetime
    sla_days: int
    breached: tuple[AwaitingDecisionRow, ...]
    page_decision: PageDecision | None

    @property
    def breach_count(self) -> int:
        return len(self.breached)


class ModelLifecycleAlertService:
    """Fire ``PROVIDER_DECISION_OVERDUE`` when candidates breach the SLA."""

    def __init__(
        self,
        lifecycle: ModelLifecycleService,
        router: IncidentRouter,
        notifier: PageNotifier,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._router = router
        self._notifier = notifier
        self._clock = clock or (lambda: datetime.now(UTC))

    def check_overdue_decisions(
        self,
        *,
        tenant_id: UUID,
        sla: timedelta = DEFAULT_DECISION_SLA,
    ) -> OverdueCheckReport:
        now = self._clock()
        rows = self._lifecycle.awaiting_decision(
            tenant_id=tenant_id,
            sla=sla,
            now=now,
        )
        breached = tuple(r for r in rows if r.sla_breached)
        if not breached:
            return OverdueCheckReport(
                checked_at=now,
                sla_days=int(sla.total_seconds() // 86400) or 1,
                breached=(),
                page_decision=None,
            )

        alert = self._build_alert(breached=breached, sla=sla, now=now)
        decision = self._router.route(alert)
        page_decision = self._notifier.page(decision)
        return OverdueCheckReport(
            checked_at=now,
            sla_days=int(sla.total_seconds() // 86400) or 1,
            breached=breached,
            page_decision=page_decision,
        )

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _build_alert(
        *,
        breached: tuple[AwaitingDecisionRow, ...],
        sla: timedelta,
        now: datetime,
    ) -> Alert:
        sla_days = int(sla.total_seconds() // 86400) or 1
        oldest_age = max(row.age_days for row in breached)
        summary = (
            f"{len(breached)} model registry candidate"
            f"{'s' if len(breached) != 1 else ''} breached the "
            f"{sla_days}-day go/no-go SLA"
        )
        detail_lines = [
            f"- {row.entry.provider}/{row.entry.model_id} — {row.age_days} days old"
            for row in breached
        ]
        return Alert(
            kind=AlertKind.PROVIDER_DECISION_OVERDUE,
            summary=summary,
            fired_at=now,
            detail="\n".join(detail_lines),
            tags={
                "breach_count": str(len(breached)),
                "sla_days": str(sla_days),
                "oldest_age_days": str(oldest_age),
            },
            extra={
                "entries": [
                    {
                        "entry_id": str(row.entry.id),
                        "provider": row.entry.provider,
                        "model_id": row.entry.model_id,
                        "family": row.entry.family,
                        "age_days": row.age_days,
                    }
                    for row in breached
                ],
            },
        )


__all__ = [
    "ModelLifecycleAlertService",
    "OverdueCheckReport",
]
