"""Unit tests for DormantUserReviewService — TD-011 / Story 6.5.2.

The bridge between :class:`AccessReviewService.snapshot` and the
:class:`DormantUserNotifier`. Covers:

* No dormant users → no notifications fired, audit silent.
* Dormant users → one notification per row, audit records the
  aggregate action with the user IDs as payload.
* Active users in the same snapshot are not notified.
* Custom review window passes through to both the snapshot and the
  notification payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import User
from qaforge_api.notifications import (
    DormantUserNotification,
    LogDormantUserNotifier,
)
from qaforge_api.services.access_review import AccessReviewService
from qaforge_api.services.dormant_user_review import (
    DormantNotificationReport,
    DormantUserReviewService,
)

_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id=_TENANT,
        user_id=_USER,
        correlation_id="trace-dormant",
    )


def _user(*, email: str, name: str, role: str = "engineer") -> User:
    u = User(email=email, name=name, role=role)
    u.id = uuid.uuid4()
    u.tenant_id = _TENANT
    return u


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _ExecuteResult:
    def __init__(self, rows: list[tuple[UUID, datetime, int]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[UUID, datetime, int]]:
        return list(self._rows)


class _StubSession:
    def __init__(
        self,
        *,
        users: list[User],
        activity: dict[UUID, tuple[datetime, int]],
    ) -> None:
        self._users = users
        self._activity = activity

    def scalars(self, stmt: Any) -> _ScalarResult:
        return _ScalarResult(self._users)

    def execute(self, stmt: Any) -> _ExecuteResult:
        rows = [
            (uid, last, count) for uid, (last, count) in self._activity.items()
        ]
        return _ExecuteResult(rows)


class _CapturingNotifier:
    def __init__(self) -> None:
        self.calls: list[DormantUserNotification] = []

    def notify_dormant(self, payload: DormantUserNotification) -> None:
        self.calls.append(payload)


class _RecordingAudit:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _build(
    *,
    users: list[User],
    activity: dict[UUID, tuple[datetime, int]],
    audit: _RecordingAudit | None = None,
) -> tuple[DormantUserReviewService, _CapturingNotifier, _RecordingAudit | None]:
    session = _StubSession(users=users, activity=activity)
    access = AccessReviewService(session, clock=lambda: _NOW)  # type: ignore[arg-type]
    notifier = _CapturingNotifier()
    bridge = DormantUserReviewService(
        access,
        notifier,
        audit=audit,  # type: ignore[arg-type]
        clock=lambda: _NOW,
    )
    return bridge, notifier, audit


# ---------------------------------------------------------------- no dormant


def test_no_users_means_no_notifications() -> None:
    bridge, notifier, _ = _build(users=[], activity={})
    report = bridge.notify_dormant_users(context=_ctx())
    assert isinstance(report, DormantNotificationReport)
    assert report.dormant_count == 0
    assert report.notified == ()
    assert notifier.calls == []


def test_all_active_users_means_no_notifications() -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob")
    bridge, notifier, _ = _build(
        users=[alice, bob],
        activity={
            alice.id: (_NOW - timedelta(days=2), 5),
            bob.id: (_NOW - timedelta(days=10), 3),
        },
    )
    report = bridge.notify_dormant_users(context=_ctx())
    assert report.dormant_count == 0
    assert notifier.calls == []


# ---------------------------------------------------------------- dormant present


def test_dormant_user_triggers_one_notification() -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob", role="admin")
    bridge, notifier, _ = _build(
        users=[alice, bob],
        activity={
            alice.id: (_NOW - timedelta(days=2), 5),
            # bob is dormant (no activity in window)
        },
    )
    report = bridge.notify_dormant_users(context=_ctx())

    assert report.dormant_count == 1
    assert len(notifier.calls) == 1
    payload = notifier.calls[0]
    assert payload.user_id == bob.id
    assert payload.email == "bob@example.com"
    assert payload.role == "admin"
    assert payload.last_seen_at is None
    assert payload.review_window_days == 90
    assert payload.tenant_id == _TENANT
    assert payload.correlation_id == "trace-dormant"


def test_active_user_in_same_snapshot_is_not_notified() -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob")
    bridge, notifier, _ = _build(
        users=[alice, bob],
        activity={
            alice.id: (_NOW - timedelta(days=2), 5),
        },
    )
    bridge.notify_dormant_users(context=_ctx())
    notified_ids = {p.user_id for p in notifier.calls}
    assert alice.id not in notified_ids
    assert bob.id in notified_ids


def test_multiple_dormant_users_are_each_notified() -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob")
    carol = _user(email="carol@example.com", name="Carol")
    bridge, notifier, _ = _build(
        users=[alice, bob, carol],
        activity={
            alice.id: (_NOW - timedelta(days=2), 5),
            # bob + carol both dormant
        },
    )
    report = bridge.notify_dormant_users(context=_ctx())
    assert report.dormant_count == 2
    assert len(notifier.calls) == 2
    assert {p.email for p in notifier.calls} == {
        "bob@example.com",
        "carol@example.com",
    }


# ---------------------------------------------------------------- audit


def test_audit_records_aggregate_event_when_anything_notified() -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob")
    audit = _RecordingAudit()
    bridge, _, _ = _build(
        users=[alice, bob],
        activity={alice.id: (_NOW - timedelta(days=2), 5)},
        audit=audit,
    )
    bridge.notify_dormant_users(context=_ctx())
    assert len(audit.calls) == 1
    call = audit.calls[0]
    assert call["action"] == "access_review.dormant_users_notified"
    assert call["resource_type"] == "user"
    assert call["resource_id"] is None
    assert call["payload"]["dormant_count"] == 1
    assert call["payload"]["notified_user_ids"] == [str(bob.id)]


def test_audit_silent_when_nothing_to_notify() -> None:
    """A successful sweep that finds nothing should not pollute the
    audit log — the runtime cadence will be loud enough on its own."""
    audit = _RecordingAudit()
    bridge, _, _ = _build(users=[], activity={}, audit=audit)
    bridge.notify_dormant_users(context=_ctx())
    assert audit.calls == []


# ---------------------------------------------------------------- window override


def test_custom_window_passes_through_to_payload() -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bridge, notifier, _ = _build(
        users=[alice],
        activity={},
    )
    report = bridge.notify_dormant_users(
        context=_ctx(),
        window=timedelta(days=30),
    )
    assert report.window_days == 30
    assert notifier.calls[0].review_window_days == 30


# ---------------------------------------------------------------- log notifier composes


def test_bridge_composes_with_log_notifier(caplog: pytest.LogCaptureFixture) -> None:
    """The default LogDormantUserNotifier should compose with the
    bridge without any glue beyond the constructor."""
    alice = _user(email="alice@example.com", name="Alice")
    session = _StubSession(users=[alice], activity={})
    access = AccessReviewService(session, clock=lambda: _NOW)  # type: ignore[arg-type]
    bridge = DormantUserReviewService(
        access,
        LogDormantUserNotifier(),
        clock=lambda: _NOW,
    )
    report = bridge.notify_dormant_users(context=_ctx())
    assert report.dormant_count == 1
