"""RetentionSweepService — Story 6.5.1.

Prunes rows past their data-class retention window per
``docs/security/data-handling.md``. Audit events are
**compliance-locked** (7-year retention) and are *never* swept by
this path; the service refuses to delete them and surfaces the skip
in the report instead, so an operator can see at a glance that the
lock held.

The class registry is authoritative for which tables get swept and
the default window. Per-workspace overrides live in
``WorkspacePolicy`` (Story 1.1.3) and are *not yet* honoured here —
that's tracked as a follow-up in ``docs/tech-debt.md`` because the
policy YAML schema doesn't pin a retention key today.

The sweep runs as a single SQL DELETE per class. Rows are matched
by the class's observed-column (``created_at`` for the common case,
``observed_at`` for the flakiness ledger, ``submitted_at`` for
agent feedback). The service emits one audit event per call, and a
dry run returns the same shape with ``deleted=0`` and a populated
``would_delete`` field so a Monday operator preview is safe.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.base import Base
from qaforge_api.db.models import (
    AgentFeedback,
    AgentTask,
    AuditEvent,
    EvidenceArtifact,
    ExternalIssue,
    FailureClassification,
    FlakinessObservation,
    TestRun,
    UsageRecordRow,
)
from qaforge_api.services.audit import AuditService

# Defaults mirror docs/security/data-handling.md. Audit events are
# compliance-locked at 7 years; everything else follows the table.
SEVEN_YEARS_DAYS = 365 * 7


@dataclass(frozen=True, slots=True)
class RetentionClass:
    """One sweepable data class."""

    name: str
    model: type[Base]
    observed_column: str
    default_days: int
    compliance_locked: bool = False


DEFAULT_RETENTION_CLASSES: tuple[RetentionClass, ...] = (
    RetentionClass(
        name="audit_events",
        model=AuditEvent,
        observed_column="created_at",
        default_days=SEVEN_YEARS_DAYS,
        compliance_locked=True,
    ),
    RetentionClass(
        name="test_runs",
        model=TestRun,
        observed_column="created_at",
        default_days=90,
    ),
    RetentionClass(
        name="agent_tasks",
        model=AgentTask,
        observed_column="created_at",
        default_days=90,
    ),
    RetentionClass(
        name="evidence_artifacts",
        model=EvidenceArtifact,
        observed_column="created_at",
        default_days=90,
    ),
    RetentionClass(
        name="failure_classifications",
        model=FailureClassification,
        observed_column="created_at",
        default_days=90,
    ),
    RetentionClass(
        name="flakiness_observations",
        model=FlakinessObservation,
        observed_column="observed_at",
        default_days=90,
    ),
    RetentionClass(
        name="agent_feedback",
        model=AgentFeedback,
        observed_column="submitted_at",
        default_days=365,
    ),
    RetentionClass(
        name="usage_records",
        model=UsageRecordRow,
        observed_column="created_at",
        default_days=365,
    ),
    RetentionClass(
        name="external_issues",
        model=ExternalIssue,
        observed_column="created_at",
        default_days=365,
    ),
)


@dataclass(frozen=True, slots=True)
class ClassSweepResult:
    """Outcome of a single retention class."""

    name: str
    cutoff: datetime
    default_days: int
    compliance_locked: bool
    deleted: int
    would_delete: int
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cutoff": self.cutoff.isoformat(),
            "default_days": self.default_days,
            "compliance_locked": self.compliance_locked,
            "deleted": self.deleted,
            "would_delete": self.would_delete,
            "skipped_reason": self.skipped_reason,
        }


@dataclass(frozen=True, slots=True)
class SweepReport:
    """Full report from one :meth:`RetentionSweepService.sweep` call."""

    started_at: datetime
    finished_at: datetime
    dry_run: bool
    classes: tuple[ClassSweepResult, ...] = field(default_factory=tuple)

    @property
    def total_deleted(self) -> int:
        return sum(c.deleted for c in self.classes)

    @property
    def total_would_delete(self) -> int:
        return sum(c.would_delete for c in self.classes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "dry_run": self.dry_run,
            "total_deleted": self.total_deleted,
            "total_would_delete": self.total_would_delete,
            "classes": [c.to_dict() for c in self.classes],
        }


class RetentionSweepService:
    def __init__(
        self,
        session: Session,
        *,
        audit: AuditService | None = None,
        classes: Sequence[RetentionClass] = DEFAULT_RETENTION_CLASSES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._audit = audit
        self._classes = tuple(classes)
        self._clock = clock or (lambda: datetime.now(UTC))

    def sweep(
        self,
        *,
        context: RequestContext,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> SweepReport:
        started = now or self._clock()
        results: list[ClassSweepResult] = []
        for cls in self._classes:
            results.append(self._sweep_class(cls=cls, now=started, dry_run=dry_run))
        finished = self._clock()
        report = SweepReport(
            started_at=started,
            finished_at=finished,
            dry_run=dry_run,
            classes=tuple(results),
        )
        if self._audit is not None:
            self._audit.record(
                context=context,
                action=(
                    "compliance.retention.dry_run"
                    if dry_run
                    else "compliance.retention.swept"
                ),
                resource_type="retention_sweep",
                resource_id=None,
                payload={
                    "total_deleted": report.total_deleted,
                    "total_would_delete": report.total_would_delete,
                    "classes": [
                        {
                            "name": c.name,
                            "deleted": c.deleted,
                            "would_delete": c.would_delete,
                            "compliance_locked": c.compliance_locked,
                        }
                        for c in report.classes
                    ],
                },
            )
        return report

    # ---------------------------------------------------- per-class

    def _sweep_class(
        self, *, cls: RetentionClass, now: datetime, dry_run: bool
    ) -> ClassSweepResult:
        cutoff = now - timedelta(days=cls.default_days)
        if cls.compliance_locked:
            return ClassSweepResult(
                name=cls.name,
                cutoff=cutoff,
                default_days=cls.default_days,
                compliance_locked=True,
                deleted=0,
                would_delete=0,
                skipped_reason="compliance_locked",
            )
        column = self._column(cls)
        count_stmt = (
            select(func.count())
            .select_from(cls.model)
            .where(column < cutoff)
        )
        would_delete = int(self._session.scalar(count_stmt) or 0)
        deleted = 0
        if not dry_run and would_delete > 0:
            delete_stmt = delete(cls.model).where(column < cutoff)
            result: CursorResult[Any] = self._session.execute(delete_stmt)  # type: ignore[assignment]
            deleted = int(result.rowcount or 0)
            self._session.flush()
        return ClassSweepResult(
            name=cls.name,
            cutoff=cutoff,
            default_days=cls.default_days,
            compliance_locked=False,
            deleted=deleted,
            would_delete=would_delete,
        )

    @staticmethod
    def _column(cls: RetentionClass) -> Any:
        column = getattr(cls.model, cls.observed_column, None)
        if column is None:
            raise RetentionConfigurationError(
                f"retention class {cls.name!r} references missing column "
                f"{cls.observed_column!r} on {cls.model.__name__}"
            )
        return column


class RetentionConfigurationError(Exception):
    """Raised when a registered class points at a column the model lacks."""


__all__ = [
    "DEFAULT_RETENTION_CLASSES",
    "SEVEN_YEARS_DAYS",
    "ClassSweepResult",
    "RetentionClass",
    "RetentionConfigurationError",
    "RetentionSweepService",
    "SweepReport",
]
