"""RetentionSweepService — Story 6.5.1.

Prunes rows past their data-class retention window per
``docs/security/data-handling.md``. Audit events are
**compliance-locked** (7-year retention) and are *never* swept by
this path; the service refuses to delete them and surfaces the skip
in the report instead, so an operator can see at a glance that the
lock held.

The class registry is authoritative for which tables get swept and
the default window. **Per-workspace overrides** (TD-009) live in the
active ``WorkspacePolicy`` (Story 1.1.3) under the ``retention`` key
— a ``{class_name: days}`` map validated by
``aqao_api.policies.schema.AgentPolicy``. At sweep time the service
reads the active policies for the tenant (RLS-scoped) and, for each
overridable class, partitions the delete into buckets: a default
bucket for every workspace *without* an override plus one bucket per
overriding workspace using that workspace's window. Overrides are
bounded to ``RETENTION_MAX_DAYS`` and may only target classes with a
direct ``workspace_id`` column; compliance-locked classes (audit
events) are never overridable.

Rows are matched by the class's observed-column (``created_at`` for
the common case, ``observed_at`` for the flakiness ledger,
``submitted_at`` for agent feedback). The service emits one audit
event per call, and a dry run returns the same shape with
``deleted=0`` and a populated ``would_delete`` field so a Monday
operator preview is safe.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, CursorResult, and_, delete, func, or_, select
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.base import Base
from aqao_api.db.models import (
    AgentFeedback,
    AgentTask,
    AuditEvent,
    EvidenceArtifact,
    ExternalIssue,
    FailureClassification,
    FlakinessObservation,
    TestRun,
    UsageRecordRow,
    WorkspacePolicy,
)
from aqao_api.policies.schema import OVERRIDABLE_RETENTION_CLASSES
from aqao_api.services.audit import AuditService

# {workspace_id: {retention_class_name: window_days}}.
RetentionOverrides = Mapping[uuid.UUID, Mapping[str, int]]
RetentionOverrideProvider = Callable[[Session], RetentionOverrides]

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


def load_active_retention_overrides(
    session: Session,
) -> dict[uuid.UUID, dict[str, int]]:
    """Read per-workspace retention overrides from active policies (TD-009).

    Returns ``{workspace_id: {class_name: days}}`` for the tenant the session
    is scoped to (RLS already filters to the caller's tenant). Only keys in
    :data:`OVERRIDABLE_RETENTION_CLASSES` are kept; the policy schema has
    already validated bounds at save time, so this is a defensive read rather
    than a re-validation.
    """
    stmt = select(WorkspacePolicy.workspace_id, WorkspacePolicy.parsed).where(
        WorkspacePolicy.active.is_(True)
    )
    overrides: dict[uuid.UUID, dict[str, int]] = {}
    for workspace_id, parsed in session.execute(stmt):
        if not isinstance(parsed, dict):
            continue
        section = parsed.get("retention")
        if not isinstance(section, dict):
            continue
        ws_overrides = {
            name: int(days)
            for name, days in section.items()
            if name in OVERRIDABLE_RETENTION_CLASSES and isinstance(days, int)
        }
        if ws_overrides:
            overrides[workspace_id] = ws_overrides
    return overrides


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
    # Number of workspaces whose own retention window (not the default) was
    # applied to this class for this sweep. 0 means the default window only.
    override_workspaces: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cutoff": self.cutoff.isoformat(),
            "default_days": self.default_days,
            "compliance_locked": self.compliance_locked,
            "deleted": self.deleted,
            "would_delete": self.would_delete,
            "skipped_reason": self.skipped_reason,
            "override_workspaces": self.override_workspaces,
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


@dataclass(frozen=True, slots=True)
class _SweepBucket:
    """One DELETE scope within a class sweep.

    ``workspace_id`` set → restrict to that workspace (an override bucket).
    ``workspace_id`` None → the default bucket: every workspace *without* an
    override, expressed as ``workspace_id NOT IN exclude`` (NULL-safe).
    """

    cutoff: datetime
    workspace_id: uuid.UUID | None = None
    exclude_workspace_ids: tuple[uuid.UUID, ...] = ()


class RetentionSweepService:
    def __init__(
        self,
        session: Session,
        *,
        audit: AuditService | None = None,
        classes: Sequence[RetentionClass] = DEFAULT_RETENTION_CLASSES,
        clock: Callable[[], datetime] | None = None,
        override_provider: RetentionOverrideProvider | None = None,
    ) -> None:
        self._session = session
        self._audit = audit
        self._classes = tuple(classes)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._override_provider = override_provider or load_active_retention_overrides

    def sweep(
        self,
        *,
        context: RequestContext,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> SweepReport:
        started = now or self._clock()
        overrides = self._override_provider(self._session)
        results: list[ClassSweepResult] = []
        for cls in self._classes:
            class_overrides = self._class_overrides(cls, overrides)
            results.append(
                self._sweep_class(
                    cls=cls,
                    now=started,
                    dry_run=dry_run,
                    class_overrides=class_overrides,
                )
            )
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
                            "override_workspaces": c.override_workspaces,
                        }
                        for c in report.classes
                    ],
                },
            )
        return report

    # ---------------------------------------------------- per-class

    @staticmethod
    def _class_overrides(
        cls: RetentionClass, overrides: RetentionOverrides
    ) -> dict[uuid.UUID, int]:
        """Project the tenant-wide override map down to one class."""
        if cls.compliance_locked or cls.name not in OVERRIDABLE_RETENTION_CLASSES:
            return {}
        out: dict[uuid.UUID, int] = {}
        for ws_id, ws_map in overrides.items():
            days = ws_map.get(cls.name)
            if days is not None:
                out[ws_id] = days
        return out

    @staticmethod
    def _plan_buckets(
        *,
        now: datetime,
        default_days: int,
        class_overrides: Mapping[uuid.UUID, int],
    ) -> list[_SweepBucket]:
        """Partition a class sweep into one cutoff scope per distinct window.

        With no overrides this is a single default bucket — identical to the
        pre-TD-009 behaviour. With overrides, the default bucket excludes the
        overriding workspaces and each of those gets its own bucket.
        """
        default_cutoff = now - timedelta(days=default_days)
        if not class_overrides:
            return [_SweepBucket(cutoff=default_cutoff)]
        overriding_ids = tuple(sorted(class_overrides, key=str))
        buckets = [
            _SweepBucket(cutoff=default_cutoff, exclude_workspace_ids=overriding_ids)
        ]
        buckets.extend(
            _SweepBucket(
                cutoff=now - timedelta(days=class_overrides[ws_id]),
                workspace_id=ws_id,
            )
            for ws_id in overriding_ids
        )
        return buckets

    def _sweep_class(
        self,
        *,
        cls: RetentionClass,
        now: datetime,
        dry_run: bool,
        class_overrides: Mapping[uuid.UUID, int],
    ) -> ClassSweepResult:
        default_cutoff = now - timedelta(days=cls.default_days)
        if cls.compliance_locked:
            return ClassSweepResult(
                name=cls.name,
                cutoff=default_cutoff,
                default_days=cls.default_days,
                compliance_locked=True,
                deleted=0,
                would_delete=0,
                skipped_reason="compliance_locked",
            )
        column = self._column(cls)
        ws_column = getattr(cls.model, "workspace_id", None)
        if class_overrides and ws_column is None:
            raise RetentionConfigurationError(
                f"retention class {cls.name!r} has per-workspace overrides but no "
                f"workspace_id column on {cls.model.__name__}"
            )
        buckets = self._plan_buckets(
            now=now, default_days=cls.default_days, class_overrides=class_overrides
        )
        total_would = 0
        total_deleted = 0
        for bucket in buckets:
            predicate = self._bucket_predicate(column, ws_column, bucket)
            would, deleted = self._count_and_delete(
                predicate=predicate, model=cls.model, dry_run=dry_run
            )
            total_would += would
            total_deleted += deleted
        return ClassSweepResult(
            name=cls.name,
            cutoff=default_cutoff,
            default_days=cls.default_days,
            compliance_locked=False,
            deleted=total_deleted,
            would_delete=total_would,
            override_workspaces=len(class_overrides),
        )

    @staticmethod
    def _bucket_predicate(
        column: Any, ws_column: Any, bucket: _SweepBucket
    ) -> ColumnElement[bool]:
        aged_out: ColumnElement[bool] = column < bucket.cutoff
        if bucket.workspace_id is not None:
            return and_(aged_out, ws_column == bucket.workspace_id)
        if bucket.exclude_workspace_ids:
            return and_(
                aged_out,
                or_(
                    ws_column.is_(None),
                    ws_column.notin_(bucket.exclude_workspace_ids),
                ),
            )
        return aged_out

    def _count_and_delete(
        self, *, predicate: ColumnElement[bool], model: type[Base], dry_run: bool
    ) -> tuple[int, int]:
        count_stmt = select(func.count()).select_from(model).where(predicate)
        would_delete = int(self._session.scalar(count_stmt) or 0)
        deleted = 0
        if not dry_run and would_delete > 0:
            result: CursorResult[Any] = self._session.execute(  # type: ignore[assignment]
                delete(model).where(predicate)
            )
            deleted = int(result.rowcount or 0)
            self._session.flush()
        return would_delete, deleted

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
    "RetentionOverrideProvider",
    "RetentionOverrides",
    "RetentionSweepService",
    "SweepReport",
    "load_active_retention_overrides",
]
