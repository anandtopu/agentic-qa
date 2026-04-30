"""Unit tests for RetentionSweepService — Story 6.5.1.

The DB-backed sweep is exercised in the integration suite (Postgres
+ RLS); here we validate the in-process orchestration: the service
respects the cutoff, never sweeps compliance-locked classes, and
the dry-run path commits no DELETEs while still reporting counts.

The stub session replays a fixed-shape SELECT-count and DELETE
contract so the orchestration is testable without a database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import AgentFeedback, AuditEvent, TestRun
from qaforge_api.services.retention import (
    SEVEN_YEARS_DAYS,
    RetentionClass,
    RetentionSweepService,
)

_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id=_TENANT,
        user_id=uuid.uuid4(),
        correlation_id="trace-retention",
    )


@pytest.fixture
def fixed_clock() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


class _StubResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _StubSession:
    """Minimal session that fakes scalar(count) + execute(delete) + flush."""

    def __init__(self, *, present: dict[str, list[datetime]]) -> None:
        self.present = present
        self.deleted: dict[str, int] = {}
        self.flushed = 0
        self.last_count_for: str | None = None

    # --- writer ---

    def execute(self, stmt: Any) -> _StubResult:
        table_name = self._extract_table(stmt)
        cutoff = self._extract_cutoff(stmt)
        before = self.present.get(table_name, [])
        kept = [t for t in before if t >= cutoff]
        removed = len(before) - len(kept)
        self.present[table_name] = kept
        self.deleted[table_name] = self.deleted.get(table_name, 0) + removed
        return _StubResult(rowcount=removed)

    def flush(self) -> None:
        self.flushed += 1

    # --- reader ---

    def scalar(self, stmt: Any) -> int:
        table_name = self._extract_table(stmt)
        cutoff = self._extract_cutoff(stmt)
        rows = self.present.get(table_name, [])
        return sum(1 for t in rows if t < cutoff)

    # --- helpers ---

    @staticmethod
    def _extract_table(stmt: Any) -> str:
        s = str(stmt).lower()
        for candidate in (
            "audit_events",
            "test_runs",
            "agent_tasks",
            "evidence_artifacts",
            "failure_classifications",
            "flakiness_observations",
            "agent_feedback",
            "usage_records",
            "external_issues",
        ):
            if candidate in s:
                return candidate
        raise AssertionError(f"unrecognised statement: {s}")

    @staticmethod
    def _extract_cutoff(stmt: Any) -> datetime:
        # SQLAlchemy stashes the bind values on the compiled statement.
        # For our where-clauses we always have one cutoff bind.
        compiled = stmt.compile(compile_kwargs={"literal_binds": False})
        for value in compiled.params.values():
            if isinstance(value, datetime):
                return value
        # Fall back: walk the where clause (less robust but works for our shape).
        where = getattr(stmt, "_where_criteria", None) or getattr(
            stmt, "whereclause", None
        )
        if where is not None:
            for child in getattr(where, "get_children", lambda: [])():
                value = getattr(getattr(child, "right", None), "value", None)
                if isinstance(value, datetime):
                    return value
        raise AssertionError("no datetime cutoff found in statement")


def _classes_for_test() -> tuple[RetentionClass, ...]:
    """Compact fixture set covering the three behaviours that matter."""
    return (
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
            name="agent_feedback",
            model=AgentFeedback,
            observed_column="submitted_at",
            default_days=365,
        ),
    )


def _build(
    fixed_clock: datetime,
    *,
    present: dict[str, list[datetime]],
    audit: Any | None = None,
) -> tuple[RetentionSweepService, _StubSession]:
    session = _StubSession(present=present)
    svc = RetentionSweepService(
        session,  # type: ignore[arg-type]
        audit=audit,
        classes=_classes_for_test(),
        clock=lambda: fixed_clock,
    )
    return svc, session


# ---------------------------------------------------- compliance lock


def test_audit_events_are_never_swept(fixed_clock: datetime) -> None:
    old = fixed_clock - timedelta(days=SEVEN_YEARS_DAYS + 30)
    present: dict[str, list[datetime]] = {
        "audit_events": [old, old, old],
        "test_runs": [],
        "agent_feedback": [],
    }
    svc, session = _build(fixed_clock, present=present)
    report = svc.sweep(context=_ctx())
    audit_result = next(c for c in report.classes if c.name == "audit_events")
    assert audit_result.compliance_locked is True
    assert audit_result.deleted == 0
    assert audit_result.would_delete == 0
    assert audit_result.skipped_reason == "compliance_locked"
    # Stub assertion: the rows are still in place — sweep didn't even attempt
    # a DELETE on the compliance-locked class.
    assert len(session.present["audit_events"]) == 3


# ---------------------------------------------------- cutoff math


def test_only_rows_older_than_cutoff_are_swept(fixed_clock: datetime) -> None:
    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [
            fixed_clock - timedelta(days=120),  # past 90d → swept
            fixed_clock - timedelta(days=100),  # past 90d → swept
            fixed_clock - timedelta(days=80),  # within 90d → kept
            fixed_clock - timedelta(days=10),  # fresh → kept
        ],
        "agent_feedback": [],
    }
    svc, session = _build(fixed_clock, present=present)
    report = svc.sweep(context=_ctx())
    test_runs = next(c for c in report.classes if c.name == "test_runs")
    assert test_runs.deleted == 2
    assert test_runs.would_delete == 2
    assert test_runs.cutoff == fixed_clock - timedelta(days=90)
    assert len(session.present["test_runs"]) == 2


def test_window_is_per_class(fixed_clock: datetime) -> None:
    """test_runs is 90d, agent_feedback is 365d — same age handled differently."""
    age_120 = fixed_clock - timedelta(days=120)
    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [age_120],
        "agent_feedback": [age_120],
    }
    svc, _ = _build(fixed_clock, present=present)
    report = svc.sweep(context=_ctx())
    by = {c.name: c for c in report.classes}
    assert by["test_runs"].deleted == 1
    assert by["agent_feedback"].deleted == 0  # 120d < 365d → safe


# ---------------------------------------------------- dry run


def test_dry_run_reports_but_does_not_delete(fixed_clock: datetime) -> None:
    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [
            fixed_clock - timedelta(days=200),
            fixed_clock - timedelta(days=200),
        ],
        "agent_feedback": [],
    }
    svc, session = _build(fixed_clock, present=present)
    report = svc.sweep(context=_ctx(), dry_run=True)
    test_runs = next(c for c in report.classes if c.name == "test_runs")
    assert report.dry_run is True
    assert report.total_deleted == 0
    assert report.total_would_delete == 2
    assert test_runs.deleted == 0
    assert test_runs.would_delete == 2
    # Rows are still in place after the dry run.
    assert len(session.present["test_runs"]) == 2


# ---------------------------------------------------- audit emission


def test_sweep_emits_audit_event_with_summary(fixed_clock: datetime) -> None:
    captured: list[dict[str, Any]] = []

    class _RecordingAudit:
        def record(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [fixed_clock - timedelta(days=200)],
        "agent_feedback": [],
    }
    svc, _ = _build(fixed_clock, present=present, audit=_RecordingAudit())
    svc.sweep(context=_ctx())
    assert len(captured) == 1
    event = captured[0]
    assert event["action"] == "compliance.retention.swept"
    assert event["resource_type"] == "retention_sweep"
    assert event["payload"]["total_deleted"] == 1
    locked_payload = next(
        c for c in event["payload"]["classes"] if c["name"] == "audit_events"
    )
    assert locked_payload["compliance_locked"] is True


def test_dry_run_audit_action_is_distinct(fixed_clock: datetime) -> None:
    captured: list[dict[str, Any]] = []

    class _RecordingAudit:
        def record(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [],
        "agent_feedback": [],
    }
    svc, _ = _build(fixed_clock, present=present, audit=_RecordingAudit())
    svc.sweep(context=_ctx(), dry_run=True)
    assert captured[0]["action"] == "compliance.retention.dry_run"


def test_report_aggregates_totals(fixed_clock: datetime) -> None:
    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [fixed_clock - timedelta(days=120)],
        "agent_feedback": [
            fixed_clock - timedelta(days=400),
            fixed_clock - timedelta(days=400),
        ],
    }
    svc, _ = _build(fixed_clock, present=present)
    report = svc.sweep(context=_ctx())
    assert report.total_deleted == 3
    assert report.total_would_delete == 3


def test_zero_rows_present_is_clean(fixed_clock: datetime) -> None:
    present: dict[str, list[datetime]] = {
        "audit_events": [],
        "test_runs": [],
        "agent_feedback": [],
    }
    svc, _ = _build(fixed_clock, present=present)
    report = svc.sweep(context=_ctx())
    assert report.total_deleted == 0
    assert all(c.would_delete == 0 for c in report.classes)
