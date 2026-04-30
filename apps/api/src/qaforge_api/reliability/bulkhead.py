"""Bulkhead — Epic 4.3.

Per-key concurrency cap. The platform binds one bulkhead per
workspace so a single tenant's burst can't crowd out another tenant
on a shared worker pool. Implemented as a counting semaphore with a
``BulkheadFull`` raise on overflow; callers are expected to translate
that into HTTP 429 / retry-with-backoff at their layer.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


class BulkheadFull(RuntimeError):  # noqa: N818 - public name predates rule
    """Raised when the bulkhead has no slot left."""

    def __init__(self, name: str, capacity: int) -> None:
        super().__init__(f"bulkhead {name!r} is full (capacity={capacity})")
        self.name = name
        self.capacity = capacity


@dataclass(slots=True)
class Bulkhead:
    """Counting semaphore with a name.

    Use as a context manager via :meth:`acquire`; raises
    :class:`BulkheadFull` immediately if no slot is available so a
    queue can't form behind it.
    """

    name: str
    capacity: int
    in_use: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")

    @contextmanager
    def acquire(self) -> Iterator[None]:
        with self._lock:
            if self.in_use >= self.capacity:
                raise BulkheadFull(self.name, self.capacity)
            self.in_use += 1
        try:
            yield
        finally:
            with self._lock:
                self.in_use = max(0, self.in_use - 1)


@dataclass(slots=True)
class BulkheadRegistry:
    """Maps a key (e.g. workspace_id-as-string) to its
    :class:`Bulkhead`. Lazily creates entries with the default
    capacity so callers don't pre-register tenants."""

    default_capacity: int = 8
    bulkheads: dict[str, Bulkhead] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def for_key(self, key: str) -> Bulkhead:
        with self._lock:
            existing = self.bulkheads.get(key)
            if existing is not None:
                return existing
            new = Bulkhead(name=key, capacity=self.default_capacity)
            self.bulkheads[key] = new
            return new


__all__ = ["Bulkhead", "BulkheadFull", "BulkheadRegistry"]
