"""FlakinessService — Story 3.3.1.

Records every (test_id, passed) outcome and computes rolling
pass-rates over 14/30/90-day windows. The "flakiness score" surfaced
to the classifier (Story 3.3.2) is a *flip rate* — the fraction of
adjacent observations whose verdicts differ — not just the failure
rate, because a test that always fails is broken, not flaky.

Definitions used here:

* ``pass_rate`` — passes / total in the window.
* ``flip_rate`` — adjacent (chronological) outcomes that differ over
  total adjacent pairs in the window. ``0.0`` for a stable test
  (always passes or always fails); approaches ``1.0`` for a
  fully-non-deterministic test.
* ``flakiness_score`` — the flip-rate. The 14-day window is the
  primary signal; 30/90 are exposed for trend analysis.

The append path is :meth:`record`; the query paths are
:meth:`summary` (single test_id) and :meth:`record_test_run_outcomes`
(batch insert at the end of a test_run).
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_api.db.models import FlakinessObservation

WINDOW_14_DAYS = timedelta(days=14)
WINDOW_30_DAYS = timedelta(days=30)
WINDOW_90_DAYS = timedelta(days=90)


@dataclass(slots=True, frozen=True)
class TestOutcome:
    """One outcome to record — used in the batch path."""

    test_id: str
    passed: bool
    duration_ms: int = 0
    observed_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class WindowStats:
    """Pass-rate + flip-rate for one rolling window."""

    days: int
    observations: int
    passes: int
    failures: int
    pass_rate: float
    flip_rate: float

    def to_dict(self) -> dict[str, object]:
        return {
            "days": self.days,
            "observations": self.observations,
            "passes": self.passes,
            "failures": self.failures,
            "pass_rate": self.pass_rate,
            "flip_rate": self.flip_rate,
        }


@dataclass(slots=True, frozen=True)
class FlakinessSummary:
    """Per-test rollup returned by :meth:`FlakinessService.summary`."""

    test_id: str
    workspace_id: UUID
    flakiness_score: float
    windows: tuple[WindowStats, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "test_id": self.test_id,
            "workspace_id": str(self.workspace_id),
            "flakiness_score": self.flakiness_score,
            "windows": [w.to_dict() for w in self.windows],
        }


class FlakinessService:
    """Append + summarise the flakiness ledger."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --------------------------------------------------------- append paths

    def record(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        test_id: str,
        passed: bool,
        test_run_id: UUID | None = None,
        duration_ms: int = 0,
        observed_at: datetime | None = None,
    ) -> FlakinessObservation:
        row = FlakinessObservation(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            test_id=test_id,
            test_run_id=test_run_id,
            passed=passed,
            duration_ms=duration_ms,
            observed_at=observed_at or datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def record_test_run_outcomes(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        test_run_id: UUID,
        outcomes: Iterable[TestOutcome],
    ) -> int:
        count = 0
        for outcome in outcomes:
            self.record(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                test_id=outcome.test_id,
                passed=outcome.passed,
                test_run_id=test_run_id,
                duration_ms=outcome.duration_ms,
                observed_at=outcome.observed_at,
            )
            count += 1
        return count

    # --------------------------------------------------------- query paths

    def summary(
        self,
        *,
        workspace_id: UUID,
        test_id: str,
        now: datetime | None = None,
    ) -> FlakinessSummary:
        """Roll up the 14 / 30 / 90-day windows for one test_id."""
        moment = now or datetime.now(UTC)
        observations = self._fetch_observations(
            workspace_id=workspace_id,
            test_id=test_id,
            since=moment - WINDOW_90_DAYS,
        )
        windows: list[WindowStats] = []
        for delta in (WINDOW_14_DAYS, WINDOW_30_DAYS, WINDOW_90_DAYS):
            cutoff = moment - delta
            scoped = [o for o in observations if o.observed_at >= cutoff]
            windows.append(_window_stats(days=delta.days, observations=scoped))

        # Primary score is the 14-day flip-rate; falls back to 30 then
        # 90 as observations accumulate.
        primary = next(
            (w.flip_rate for w in windows if w.observations >= 2),
            0.0,
        )
        return FlakinessSummary(
            test_id=test_id,
            workspace_id=workspace_id,
            flakiness_score=primary,
            windows=tuple(windows),
        )

    # --------------------------------------------------------- helpers

    def _fetch_observations(
        self,
        *,
        workspace_id: UUID,
        test_id: str,
        since: datetime,
    ) -> list[FlakinessObservation]:
        stmt = (
            select(FlakinessObservation)
            .where(
                FlakinessObservation.workspace_id == workspace_id,
                FlakinessObservation.test_id == test_id,
                FlakinessObservation.observed_at >= since,
            )
            .order_by(FlakinessObservation.observed_at.asc())
        )
        return list(self._session.scalars(stmt).all())


def _window_stats(*, days: int, observations: Sequence[FlakinessObservation]) -> WindowStats:
    total = len(observations)
    if total == 0:
        return WindowStats(
            days=days,
            observations=0,
            passes=0,
            failures=0,
            pass_rate=0.0,
            flip_rate=0.0,
        )
    passes = sum(1 for o in observations if o.passed)
    failures = total - passes
    pass_rate = passes / total
    if total < 2:
        flip_rate = 0.0
    else:
        flips = sum(
            1 for prev, curr in itertools.pairwise(observations) if prev.passed != curr.passed
        )
        flip_rate = flips / (total - 1)
    return WindowStats(
        days=days,
        observations=total,
        passes=passes,
        failures=failures,
        pass_rate=pass_rate,
        flip_rate=flip_rate,
    )


__all__ = [
    "WINDOW_14_DAYS",
    "WINDOW_30_DAYS",
    "WINDOW_90_DAYS",
    "FlakinessService",
    "FlakinessSummary",
    "TestOutcome",
    "WindowStats",
]
