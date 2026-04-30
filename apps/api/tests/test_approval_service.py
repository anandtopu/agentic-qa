"""Unit tests for ApprovalService — Story 2.1.1.

The DB-backed query path (filters, RLS) is exercised under integration;
here we cover the state-machine logic, expiry handling, and audit fan-
out using a small stub session. The PRD §9.10 contract is:

    pending -> approved | rejected | expired | cancelled

and every transition is irreversible.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    ApprovalEventType,
    ApprovalRequest,
    ApprovalState,
    AuditEvent,
)
from qaforge_api.services.approval import ApprovalService
from qaforge_api.services.errors import (
    InvalidStateError,
    ResourceNotFoundError,
)


class _StubSession:
    """Minimal Session impl: holds rows in a dict keyed by (type, id)."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = 0
        self._store: dict[tuple[type, UUID], Any] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._store[(type(obj), obj.id)] = obj

    def flush(self) -> None:
        self.flushed += 1
        for obj in self.added:
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)

    def get(self, cls: type, ident: UUID) -> Any | None:
        return self._store.get((cls, ident))


@pytest.fixture
def session() -> _StubSession:
    return _StubSession()


@pytest.fixture
def context() -> RequestContext:
    return RequestContext(
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        correlation_id="trace-1",
    )


@pytest.fixture
def service(session: _StubSession) -> ApprovalService:
    return ApprovalService(session)  # type: ignore[arg-type]


def _audit_actions(session: _StubSession) -> list[str]:
    return [a.action for a in session.added if isinstance(a, AuditEvent)]


def test_request_creates_pending_with_default_ttl(
    service: ApprovalService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    moment = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    record = service.request(
        event_type=ApprovalEventType.DESTRUCTIVE_SQL,
        subject="DROP TABLE legacy_users",
        context=context,
        now=moment,
    )

    assert record.state == ApprovalState.PENDING.value
    assert record.event_type == "destructive_sql"
    assert record.requested_by == context.user_id
    assert record.expires_at == moment + timedelta(hours=24)
    assert "approval.request" in _audit_actions(session)


def test_request_accepts_string_event_type(
    service: ApprovalService,
    context: RequestContext,
) -> None:
    record = service.request(
        event_type="release_readiness",
        subject="release v2.3.0",
        context=context,
    )
    assert record.event_type == "release_readiness"


def test_request_rejects_unknown_event_type(
    service: ApprovalService, context: RequestContext
) -> None:
    with pytest.raises(ValueError):
        service.request(
            event_type="not-a-real-gate",
            subject="x",
            context=context,
        )


def test_approve_transitions_pending_to_approved(
    service: ApprovalService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    record = service.request(
        event_type=ApprovalEventType.RELEASE_READINESS,
        subject="release v1",
        context=context,
    )
    decided = service.approve(
        request_id=record.id,
        context=context,
        comment="LGTM",
    )

    assert decided.state == ApprovalState.APPROVED.value
    assert decided.decision_comment == "LGTM"
    assert decided.decided_by == context.user_id
    assert decided.decided_at is not None
    assert "approval.approved" in _audit_actions(session)


def test_reject_transitions_pending_to_rejected(
    service: ApprovalService, context: RequestContext
) -> None:
    record = service.request(
        event_type=ApprovalEventType.PRODUCTION_TEST_EXECUTION,
        subject="run on prod",
        context=context,
    )
    decided = service.reject(request_id=record.id, context=context, comment="too risky")
    assert decided.state == ApprovalState.REJECTED.value
    assert decided.decision_comment == "too risky"


def test_cancel_transitions_pending_to_cancelled(
    service: ApprovalService, context: RequestContext
) -> None:
    record = service.request(
        event_type=ApprovalEventType.HIGH_COST_EVAL_RUN,
        subject="run nightly eval",
        context=context,
    )
    decided = service.cancel(request_id=record.id, context=context)
    assert decided.state == ApprovalState.CANCELLED.value


def test_double_decision_is_rejected(service: ApprovalService, context: RequestContext) -> None:
    record = service.request(
        event_type=ApprovalEventType.DESTRUCTIVE_SQL,
        subject="DELETE",
        context=context,
    )
    service.approve(request_id=record.id, context=context)

    with pytest.raises(InvalidStateError) as exc:
        service.reject(request_id=record.id, context=context)
    assert exc.value.current_state == "approved"
    assert exc.value.attempted == "rejected"


def test_approving_after_expiry_auto_expires_and_raises(
    service: ApprovalService,
    session: _StubSession,
    context: RequestContext,
) -> None:
    created_at = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    record = service.request(
        event_type=ApprovalEventType.DESTRUCTIVE_SQL,
        subject="DROP",
        context=context,
        now=created_at,
        ttl=timedelta(hours=1),
    )

    later = created_at + timedelta(hours=2)
    with pytest.raises(InvalidStateError):
        service.approve(request_id=record.id, context=context, now=later)

    refreshed = service.get(request_id=record.id)
    assert refreshed.state == ApprovalState.EXPIRED.value
    assert "approval.expire" in _audit_actions(session)


def test_get_missing_raises_not_found(service: ApprovalService) -> None:
    with pytest.raises(ResourceNotFoundError):
        service.get(request_id=uuid.uuid4())


def test_request_propagates_workspace_and_test_run_ids(
    service: ApprovalService, context: RequestContext
) -> None:
    workspace_id = uuid.uuid4()
    test_run_id = uuid.uuid4()
    record = service.request(
        event_type=ApprovalEventType.PRODUCTION_TEST_EXECUTION,
        subject="run smoke on prod",
        context=context,
        workspace_id=workspace_id,
        test_run_id=test_run_id,
        gate_context={"command": "make smoke"},
    )
    assert record.workspace_id == workspace_id
    assert record.test_run_id == test_run_id
    assert record.context["command"] == "make smoke"


def test_approval_request_orm_columns_match_migration() -> None:
    """Cheap smoke test that the ORM model exposes every column that
    the migration creates — catches drift between the two when one is
    edited without the other."""
    columns = {c.name for c in ApprovalRequest.__table__.columns}
    expected = {
        "id",
        "tenant_id",
        "workspace_id",
        "test_run_id",
        "event_type",
        "state",
        "subject",
        "reason",
        "context",
        "requested_by",
        "decided_by",
        "decision_comment",
        "expires_at",
        "decided_at",
        "created_at",
        "updated_at",
    }
    assert columns == expected
