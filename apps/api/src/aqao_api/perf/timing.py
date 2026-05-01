"""In-process timing helper — Epic 4.5.

A :func:`time_call` context manager records the wall-clock duration
of an arbitrary block and reports it back as a :class:`TimedCall`.
Used by service-level perf assertions in tests + by the eval harness
when measuring agent latency.

The clock source is :func:`time.perf_counter_ns` so a process-local
monotonic timer can't be skewed by NTP adjustments mid-call.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class TimedCall:
    """Result of :func:`time_call`."""

    name: str
    duration_ms: int = 0


@contextmanager
def time_call(name: str) -> Iterator[TimedCall]:
    """Yield a :class:`TimedCall` and populate ``duration_ms`` on
    exit. The call shape is::

        with time_call("planner") as t:
            run_planner(...)
        assert t.duration_ms < 90_000
    """
    record = TimedCall(name=name)
    start = time.perf_counter_ns()
    try:
        yield record
    finally:
        record.duration_ms = (time.perf_counter_ns() - start) // 1_000_000


__all__ = ["TimedCall", "time_call"]
