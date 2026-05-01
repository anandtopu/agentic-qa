"""Unit tests for ModelLifecycleAlertService — TD-008 / Epic 6.2.

The bridge between :class:`ModelLifecycleService.awaiting_decision`
and the Phase-4 incident router. Covers:

* No breach → no alert fired, report carries an empty ``breached``
  tuple and a ``None`` page decision.
* One breach → alert routed to SEV4, payload includes the entry
  identifiers + age in tags/extra so the runbook has something to
  triage from.
* Multiple breaches → summary line pluralises and ``oldest_age_days``
  reflects the worst offender.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import ModelRegistryEntry
from qaforge_api.incident import (
    AlertKind,
    IncidentRouter,
    LogPageNotifier,
    PageDecision,
    Severity,
)
from qaforge_api.incident.router import RoutingDecision
from qaforge_api.services.lifecycle_alerts import (
    ModelLifecycleAlertService,
    OverdueCheckReport,
)
from qaforge_api.services.model_lifecycle import ModelLifecycleService

_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id=_TENANT,
        user_id=_USER,
        correlation_id="trace-lifecycle-alerts",
    )


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


class _StubSession:
    """In-memory session that holds ModelRegistryEntry rows. Matches the
    minimal SQLAlchemy surface the lifecycle service touches — same
    pattern as ``tests/test_model_lifecycle_service.py``."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self._by_id: dict[UUID, ModelRegistryEntry] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, ModelRegistryEntry):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = _NOW
            if obj.updated_at is None:
                obj.updated_at = _NOW
            self._by_id[obj.id] = obj

    def flush(self) -> None:
        return None

    def get(self, model: type, pk: UUID) -> Any | None:
        if model is ModelRegistryEntry:
            return self._by_id.get(pk)
        return None

    def scalars(self, stmt: Any) -> _ScalarResult:
        rows: list[ModelRegistryEntry] = list(self._by_id.values())
        where = getattr(stmt, "whereclause", None)
        if where is not None:
            rows = [r for r in rows if _matches(r, where)]
        return _ScalarResult(self._apply_order(rows, stmt))

    @staticmethod
    def _apply_order(
        rows: list[ModelRegistryEntry], stmt: Any
    ) -> list[ModelRegistryEntry]:
        order = getattr(stmt, "_order_by_clauses", None) or []
        if not order:
            return rows
        clause = order[0]
        col = getattr(clause, "element", clause)
        col_name = getattr(col, "key", None)
        if col_name is None:
            return rows
        descending = "DESC" in str(clause).upper()
        return sorted(
            rows,
            key=lambda r: getattr(r, col_name),
            reverse=descending,
        )


def _matches(row: ModelRegistryEntry, clause: Any) -> bool:
    children = list(clause.get_children()) if hasattr(clause, "get_children") else []
    op_name = getattr(getattr(clause, "operator", None), "__name__", "")
    if op_name == "and_":
        return all(_matches(row, child) for child in children)
    left = getattr(clause, "left", None)
    right = getattr(clause, "right", None)
    if left is None or right is None:
        return True
    col_name = getattr(left, "key", None)
    if col_name is None:
        return True
    value = getattr(right, "value", None)
    actual = getattr(row, col_name, None)
    if op_name == "eq":
        return actual == value
    if op_name == "is_":
        return actual is value
    if op_name == "isnot":
        return actual is not value
    return True


class _CapturingNotifier:
    """PageNotifier stub that records every page() call."""

    transport = "test-capture"

    def __init__(self) -> None:
        self.calls: list[RoutingDecision] = []

    def page(self, decision: RoutingDecision) -> PageDecision:
        self.calls.append(decision)
        return PageDecision(
            decision=decision,
            delivered_to=tuple(decision.rule.page_channels),
            transport=self.transport,
        )


def _register(
    service: ModelLifecycleService,
    *,
    provider: str,
    model_id: str,
    released_at: datetime,
    family: str | None = None,
) -> ModelRegistryEntry:
    return service.register(
        context=_ctx(),
        provider=provider,
        model_id=model_id,
        family=family,
        released_at=released_at,
    )


def _build(
    *, clock: datetime = _NOW
) -> tuple[
    ModelLifecycleService,
    ModelLifecycleAlertService,
    _CapturingNotifier,
]:
    session = _StubSession()
    lifecycle = ModelLifecycleService(
        session,  # type: ignore[arg-type]
        audit=None,
        clock=lambda: clock,
    )
    notifier = _CapturingNotifier()
    bridge = ModelLifecycleAlertService(
        lifecycle,
        IncidentRouter(),
        notifier,
        clock=lambda: clock,
    )
    return lifecycle, bridge, notifier


# ---------------------------------------------------------------- no breach


def test_no_candidates_means_no_page() -> None:
    _, bridge, notifier = _build()
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert isinstance(report, OverdueCheckReport)
    assert report.breach_count == 0
    assert report.page_decision is None
    assert notifier.calls == []


def test_unbreached_candidate_does_not_page() -> None:
    """A candidate registered 5 days ago is below the 14-day SLA."""
    lifecycle, bridge, notifier = _build()
    _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=5),
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert report.breach_count == 0
    assert report.page_decision is None
    assert notifier.calls == []


# ---------------------------------------------------------------- single breach


def test_one_breach_fires_sev4_alert() -> None:
    lifecycle, bridge, notifier = _build()
    _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=20),
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)

    assert report.breach_count == 1
    assert report.page_decision is not None
    assert len(notifier.calls) == 1

    decision = notifier.calls[0]
    assert decision.alert.kind is AlertKind.PROVIDER_DECISION_OVERDUE
    assert decision.severity is Severity.SEV4
    assert decision.alert.tags["breach_count"] == "1"
    assert decision.alert.tags["sla_days"] == "14"
    assert decision.alert.tags["oldest_age_days"] == "20"


def test_alert_summary_uses_singular_for_one_breach() -> None:
    lifecycle, bridge, _ = _build()
    _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=20),
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert report.page_decision is not None
    summary = report.page_decision.decision.alert.summary
    assert "1 model registry candidate" in summary
    # Pluralisation guard: "candidate breached" not "candidates breached".
    assert "candidates " not in summary


def test_alert_extra_carries_per_entry_identifiers() -> None:
    lifecycle, bridge, _ = _build()
    row = _register(
        lifecycle,
        provider="openai",
        model_id="gpt-9",
        family="frontier",
        released_at=_NOW - timedelta(days=18),
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert report.page_decision is not None
    entries = report.page_decision.decision.alert.extra["entries"]
    assert len(entries) == 1
    only = entries[0]
    assert only["entry_id"] == str(row.id)
    assert only["provider"] == "openai"
    assert only["model_id"] == "gpt-9"
    assert only["family"] == "frontier"
    assert only["age_days"] == 18


# ---------------------------------------------------------------- many breaches


def test_multiple_breaches_pluralise_and_track_oldest() -> None:
    lifecycle, bridge, notifier = _build()
    _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=30),
    )
    _register(
        lifecycle,
        provider="openai",
        model_id="gpt-9",
        released_at=_NOW - timedelta(days=21),
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert report.breach_count == 2
    assert len(notifier.calls) == 1
    alert = notifier.calls[0].alert
    assert "2 model registry candidates" in alert.summary
    assert alert.tags["breach_count"] == "2"
    assert alert.tags["oldest_age_days"] == "30"
    assert len(alert.extra["entries"]) == 2


def test_decided_candidate_drops_out_of_breach_set() -> None:
    """Once a decision is recorded, the bridge should not re-page on
    that row even if it was previously breached."""
    from qaforge_api.db.models import ModelDecision

    lifecycle, bridge, _notifier = _build()
    overdue = _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=30),
    )
    fresh = _register(
        lifecycle,
        provider="openai",
        model_id="gpt-9",
        released_at=_NOW - timedelta(days=20),
    )
    lifecycle.record_decision(
        context=_ctx(),
        entry_id=overdue.id,
        decision=ModelDecision.GO,
        rationale="passes evals + 12% cost win",
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert report.breach_count == 1
    assert report.breached[0].entry.id == fresh.id


# ---------------------------------------------------------------- SLA override


def test_custom_sla_changes_breach_classification() -> None:
    """A 7-day SLA catches what 14 wouldn't — useful for ops dialing
    in their own urgency."""
    lifecycle, bridge, _ = _build()
    _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=10),
    )
    default = bridge.check_overdue_decisions(tenant_id=_TENANT)
    tight = bridge.check_overdue_decisions(
        tenant_id=_TENANT, sla=timedelta(days=7)
    )
    assert default.breach_count == 0
    assert tight.breach_count == 1
    assert tight.sla_days == 7


# ---------------------------------------------------------------- log notifier


def test_log_page_notifier_emits_warning_for_sev4(caplog: pytest.LogCaptureFixture) -> None:
    """The default log notifier downgrades SEV3+ to WARNING, which is
    the right level for a queue-piling-up alert. We just confirm the
    bridge composes with the real notifier without raising."""
    session = _StubSession()
    lifecycle = ModelLifecycleService(
        session,  # type: ignore[arg-type]
        audit=None,
        clock=lambda: _NOW,
    )
    bridge = ModelLifecycleAlertService(
        lifecycle,
        IncidentRouter(),
        LogPageNotifier(),
        clock=lambda: _NOW,
    )
    _register(
        lifecycle,
        provider="anthropic",
        model_id="claude-opus-4-7",
        released_at=_NOW - timedelta(days=20),
    )
    report = bridge.check_overdue_decisions(tenant_id=_TENANT)
    assert report.page_decision is not None
    assert report.page_decision.transport == "structured-log"
