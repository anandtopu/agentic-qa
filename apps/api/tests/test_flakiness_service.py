"""Unit tests for FlakinessService — Story 3.3.1.

The DB-backed query path runs under integration; here we validate the
flip-rate / pass-rate math + window slicing using a stub session that
holds the observation rows in memory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from qaforge_api.db.models import FlakinessObservation
from qaforge_api.services.flakiness import (
    FlakinessService,
    TestOutcome,
)


class _StubSession:
    """In-memory session with enough surface for FlakinessService.

    ``scalars(stmt)`` walks the WHERE clause, filters by the literal
    column equality / >= comparisons FlakinessService builds, and
    returns the result list ordered by ``observed_at`` ascending.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def flush(self) -> None:
        self.flushed += 1

    def scalars(self, stmt: Any) -> Any:
        rows = [r for r in self.added if isinstance(r, FlakinessObservation)]
        for crit in stmt.whereclause.get_children() if stmt.whereclause is not None else []:
            if not (hasattr(crit, "left") and hasattr(crit, "right")):
                continue
            col = getattr(crit.left, "key", None)
            value = getattr(crit.right, "value", None)
            if col is None:
                continue
            op_name = crit.operator.__name__
            if op_name == "eq":
                rows = [r for r in rows if getattr(r, col) == value]
            elif op_name == "ge":
                rows = [r for r in rows if getattr(r, col) >= value]
        rows.sort(key=lambda r: r.observed_at)
        return _ScalarResult(rows)


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


@pytest.fixture
def session() -> _StubSession:
    return _StubSession()


@pytest.fixture
def service(session: _StubSession) -> FlakinessService:
    return FlakinessService(session)  # type: ignore[arg-type]


_TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_WORKSPACE = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _record_outcomes(
    service: FlakinessService,
    *,
    test_id: str,
    outcomes: list[tuple[bool, datetime]],
    workspace_id: UUID = _WORKSPACE,
) -> None:
    for passed, observed_at in outcomes:
        service.record(
            tenant_id=_TENANT,
            workspace_id=workspace_id,
            test_id=test_id,
            passed=passed,
            observed_at=observed_at,
        )


# ---------------------------------------------------------------- math


def test_summary_for_unknown_test_returns_zeroed_windows(
    service: FlakinessService,
) -> None:
    summary = service.summary(workspace_id=_WORKSPACE, test_id="ghost")
    assert summary.flakiness_score == 0.0
    assert all(w.observations == 0 for w in summary.windows)


def test_stable_test_has_zero_flip_rate_and_perfect_pass_rate(
    service: FlakinessService,
) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    _record_outcomes(
        service,
        test_id="t1",
        outcomes=[(True, base + timedelta(days=i)) for i in range(10)],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="t1",
        now=base + timedelta(days=11),
    )
    assert summary.flakiness_score == 0.0
    fourteen = summary.windows[0]
    assert fourteen.observations == 10
    assert fourteen.pass_rate == 1.0
    assert fourteen.flip_rate == 0.0


def test_always_failing_test_has_zero_flip_rate_not_flaky(
    service: FlakinessService,
) -> None:
    """A test that never passes is broken, not flaky — flip-rate is the
    right signal because it says 'how often does the verdict change?'"""
    base = datetime(2026, 5, 1, tzinfo=UTC)
    _record_outcomes(
        service,
        test_id="broken",
        outcomes=[(False, base + timedelta(days=i)) for i in range(10)],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="broken",
        now=base + timedelta(days=11),
    )
    fourteen = summary.windows[0]
    assert fourteen.flip_rate == 0.0
    assert fourteen.pass_rate == 0.0
    assert summary.flakiness_score == 0.0


def test_alternating_outcomes_have_full_flip_rate(
    service: FlakinessService,
) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    _record_outcomes(
        service,
        test_id="flaky",
        outcomes=[(i % 2 == 0, base + timedelta(days=i)) for i in range(10)],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="flaky",
        now=base + timedelta(days=11),
    )
    fourteen = summary.windows[0]
    assert fourteen.flip_rate == 1.0
    assert summary.flakiness_score == 1.0


def test_partial_flip_rate_calculated_correctly(
    service: FlakinessService,
) -> None:
    """4 observations, 1 flip: flip-rate = 1/3."""
    base = datetime(2026, 5, 1, tzinfo=UTC)
    _record_outcomes(
        service,
        test_id="some_flake",
        outcomes=[
            (True, base + timedelta(hours=1)),
            (True, base + timedelta(hours=2)),
            (False, base + timedelta(hours=3)),
            (False, base + timedelta(hours=4)),
        ],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="some_flake",
        now=base + timedelta(days=1),
    )
    assert summary.windows[0].flip_rate == pytest.approx(1 / 3)


def test_observations_outside_window_are_excluded(
    service: FlakinessService,
) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    # 14-day window snaps off observations older than 14 days from `now`.
    _record_outcomes(
        service,
        test_id="t",
        outcomes=[
            (True, base),
            (False, base + timedelta(days=20)),
            (True, base + timedelta(days=22)),
        ],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="t",
        now=base + timedelta(days=25),
    )
    fourteen = summary.windows[0]
    # Within 14d of `now=base+25d` -> only the day-20 + day-22 obs.
    assert fourteen.observations == 2
    ninety = summary.windows[2]
    assert ninety.observations == 3


def test_workspace_isolation_in_summary(service: FlakinessService) -> None:
    """An observation in a different workspace must not leak."""
    base = datetime(2026, 5, 1, tzinfo=UTC)
    other = uuid.uuid4()
    _record_outcomes(
        service,
        test_id="t",
        outcomes=[(False, base)],
        workspace_id=other,
    )
    _record_outcomes(
        service,
        test_id="t",
        outcomes=[(True, base + timedelta(hours=1))],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="t",
        now=base + timedelta(days=1),
    )
    assert summary.windows[0].observations == 1
    assert summary.windows[0].pass_rate == 1.0


def test_record_test_run_outcomes_batch_inserts(
    service: FlakinessService,
) -> None:
    test_run_id = uuid.uuid4()
    count = service.record_test_run_outcomes(
        tenant_id=_TENANT,
        workspace_id=_WORKSPACE,
        test_run_id=test_run_id,
        outcomes=[
            TestOutcome(test_id="t1", passed=True),
            TestOutcome(test_id="t2", passed=False, duration_ms=1234),
        ],
    )
    assert count == 2


def test_summary_to_dict_round_trip_shape(service: FlakinessService) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    _record_outcomes(
        service,
        test_id="t",
        outcomes=[(True, base), (False, base + timedelta(hours=1))],
    )
    summary = service.summary(
        workspace_id=_WORKSPACE,
        test_id="t",
        now=base + timedelta(days=1),
    )
    payload = summary.to_dict()
    assert payload["test_id"] == "t"
    assert "flakiness_score" in payload
    assert len(payload["windows"]) == 3
