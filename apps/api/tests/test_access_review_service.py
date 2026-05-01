"""Unit tests for AccessReviewService — Story 6.5.2.

The DB-backed snapshot runs under integration; here we validate
the in-process rollup: dormant detection, last-seen mapping, and
the per-user aggregation shape.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from aqao_api.db.models import User
from aqao_api.services.access_review import (
    DEFAULT_REVIEW_WINDOW,
    AccessReviewService,
)

_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def fixed_clock() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


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
    """Stub that returns the User list for `scalars` and the activity
    rollup for `execute`."""

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
        rows = [(uid, last, count) for uid, (last, count) in self._activity.items()]
        return _ExecuteResult(rows)


def _service(
    fixed_clock: datetime,
    *,
    users: list[User],
    activity: dict[UUID, tuple[datetime, int]],
) -> AccessReviewService:
    session = _StubSession(users=users, activity=activity)
    return AccessReviewService(session, clock=lambda: fixed_clock)  # type: ignore[arg-type]


def test_default_review_window_is_90_days() -> None:
    assert timedelta(days=90) == DEFAULT_REVIEW_WINDOW


def test_snapshot_includes_every_user(fixed_clock: datetime) -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob", role="admin")
    svc = _service(
        fixed_clock,
        users=[alice, bob],
        activity={
            alice.id: (fixed_clock - timedelta(days=2), 5),
            bob.id: (fixed_clock - timedelta(days=20), 3),
        },
    )
    snapshot = svc.snapshot(tenant_id=_TENANT)
    by_email = {e.email: e for e in snapshot.entries}
    assert set(by_email) == {"alice@example.com", "bob@example.com"}
    assert by_email["alice@example.com"].recent_action_count == 5
    assert by_email["bob@example.com"].role == "admin"


def test_user_with_no_activity_is_dormant(fixed_clock: datetime) -> None:
    alice = _user(email="alice@example.com", name="Alice")
    bob = _user(email="bob@example.com", name="Bob")
    svc = _service(
        fixed_clock,
        users=[alice, bob],
        activity={
            alice.id: (fixed_clock - timedelta(days=2), 7),
            # bob has no activity at all in window
        },
    )
    snapshot = svc.snapshot(tenant_id=_TENANT)
    by_email = {e.email: e for e in snapshot.entries}
    assert by_email["bob@example.com"].is_dormant is True
    assert by_email["bob@example.com"].last_seen_at is None
    assert by_email["bob@example.com"].recent_action_count == 0
    assert by_email["alice@example.com"].is_dormant is False
    assert snapshot.dormant_count == 1


def test_window_days_passes_through(fixed_clock: datetime) -> None:
    alice = _user(email="alice@example.com", name="Alice")
    svc = _service(
        fixed_clock,
        users=[alice],
        activity={alice.id: (fixed_clock, 1)},
    )
    snap = svc.snapshot(tenant_id=_TENANT, window=timedelta(days=30))
    assert snap.window_days == 30
    assert snap.since == fixed_clock - timedelta(days=30)


def test_snapshot_with_no_users_is_empty(fixed_clock: datetime) -> None:
    svc = _service(fixed_clock, users=[], activity={})
    snapshot = svc.snapshot(tenant_id=_TENANT)
    assert snapshot.entries == ()
    assert snapshot.dormant_count == 0
