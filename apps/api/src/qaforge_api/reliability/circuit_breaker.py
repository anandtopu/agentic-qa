"""CircuitBreaker — Epic 4.3.

Three-state CB wrapping any callable. Counts consecutive failures;
once ``failure_threshold`` is crossed, the breaker **opens** and
short-circuits subsequent calls with :class:`BreakerOpen` for
``recovery_timeout`` seconds. After the timeout it transitions to
**half-open** — one trial call decides whether to close (success) or
re-open (failure).

The PRD AC for Epic 4.3 is: "Chaos test (provider 500s for 5 min)
keeps platform operational with degraded mode." Wrapping the LLM
provider call in :class:`CircuitBreaker` and falling back to the
heuristic classifier in the open state satisfies that — see the
chaos test in :mod:`apps.api.tests.test_reliability`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerOpen(RuntimeError):  # noqa: N818 - public name predates rule
    """Raised when a call is short-circuited because the breaker is open."""

    def __init__(self, name: str, opened_at: datetime) -> None:
        super().__init__(f"circuit breaker {name!r} is open (opened at {opened_at.isoformat()})")
        self.name = name
        self.opened_at = opened_at


@dataclass(slots=True)
class CircuitBreaker:
    """Three-state circuit breaker.

    Construction is cheap so callers can build one per-provider /
    per-tenant. ``allow()`` is the only mutation surface: it returns
    after a successful call and raises after a failed one.
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: timedelta = timedelta(seconds=30)
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    opened_at: datetime | None = None
    half_open_in_flight: bool = field(default=False)

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")

    # ----------------------------------------------------- decision

    def _check_or_advance(self, *, now: datetime) -> None:
        if self.state is not BreakerState.OPEN:
            return
        assert self.opened_at is not None
        if now - self.opened_at >= self.recovery_timeout:
            # Transition to half-open; a single trial call gates closure.
            self.state = BreakerState.HALF_OPEN
            self.half_open_in_flight = False

    def before_call(self, *, now: datetime | None = None) -> None:
        """Raise :class:`BreakerOpen` if the call should not proceed."""
        moment = now or datetime.now(UTC)
        self._check_or_advance(now=moment)
        if self.state is BreakerState.OPEN:
            assert self.opened_at is not None
            raise BreakerOpen(self.name, self.opened_at)
        if self.state is BreakerState.HALF_OPEN and self.half_open_in_flight:
            assert self.opened_at is not None
            raise BreakerOpen(self.name, self.opened_at)
        if self.state is BreakerState.HALF_OPEN:
            self.half_open_in_flight = True

    def after_success(self) -> None:
        self.consecutive_failures = 0
        if self.state is BreakerState.HALF_OPEN:
            self.state = BreakerState.CLOSED
            self.opened_at = None
            self.half_open_in_flight = False

    def after_failure(self, *, now: datetime | None = None) -> None:
        moment = now or datetime.now(UTC)
        if self.state is BreakerState.HALF_OPEN:
            self.state = BreakerState.OPEN
            self.opened_at = moment
            self.half_open_in_flight = False
            return
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = BreakerState.OPEN
            self.opened_at = moment

    # ----------------------------------------------------- conveniences

    def call(
        self,
        fn: Callable[[], T],
        *,
        now: datetime | None = None,
    ) -> T:
        """Synchronous call wrapper. Re-raises whatever ``fn`` raised
        after counting it; raises :class:`BreakerOpen` if the breaker
        is open."""
        self.before_call(now=now)
        try:
            result = fn()
        except Exception:
            self.after_failure(now=now)
            raise
        self.after_success()
        return result

    async def acall(
        self,
        fn: Callable[[], Awaitable[T]],
        *,
        now: datetime | None = None,
    ) -> T:
        """Async variant of :meth:`call`."""
        self.before_call(now=now)
        try:
            result = await fn()
        except Exception:
            self.after_failure(now=now)
            raise
        self.after_success()
        return result


__all__ = ["BreakerOpen", "BreakerState", "CircuitBreaker"]
