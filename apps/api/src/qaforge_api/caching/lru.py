"""Thread-safe LRU cache with TTL — Epic 4.5.

The reference impl backs the prompt-template lookup + the HTTP-cache
layer. Production deployments swap a Redis impl by satisfying the
:class:`Cache` Protocol.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Generic, Protocol, TypeVar

K = TypeVar("K")
V = TypeVar("V")
# Cache keys are pure inputs — Protocol declarations need K to be
# contravariant. Values flow both directions so V stays invariant.
K_contra = TypeVar("K_contra", contravariant=True)


class Cache(Protocol[K_contra, V]):
    """Read/write surface every cache impl satisfies."""

    def get(self, key: K_contra) -> V | None: ...

    def set(self, key: K_contra, value: V) -> None: ...

    def get_or_compute(self, key: K_contra, factory: Callable[[], V]) -> V: ...

    def invalidate(self, key: K_contra) -> None: ...

    def clear(self) -> None: ...


@dataclass(slots=True)
class CacheStats:
    """Hit/miss counters — exposed for SLO + perf-budget tests."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0


@dataclass(slots=True)
class _Entry(Generic[V]):  # noqa: UP046 - PEP-695 syntax incompatible with method bodies that use the legacy TypeVars
    value: V
    expires_at: datetime | None


class LruCache(Generic[K, V]):  # noqa: UP046 - same as above
    """Thread-safe LRU with optional per-entry TTL.

    Capacity is the number of entries; once exceeded the
    least-recently-used entry is evicted. Reads on an expired entry
    return ``None`` and remove the entry — keeps stale data from
    accumulating without a separate sweep job.
    """

    def __init__(
        self,
        *,
        capacity: int = 1024,
        default_ttl: timedelta | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._default_ttl = default_ttl
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._lock = threading.Lock()
        self.stats = CacheStats()

    def get(self, key: K, *, now: datetime | None = None) -> V | None:
        moment = now or datetime.now(UTC)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.stats.misses += 1
                return None
            if entry.expires_at is not None and entry.expires_at <= moment:
                # Expired — evict and report a miss.
                del self._entries[key]
                self.stats.misses += 1
                return None
            self._entries.move_to_end(key)
            self.stats.hits += 1
            return entry.value

    def set(
        self,
        key: K,
        value: V,
        *,
        ttl: timedelta | None = None,
        now: datetime | None = None,
    ) -> None:
        moment = now or datetime.now(UTC)
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = moment + effective_ttl if effective_ttl is not None else None
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = _Entry(value=value, expires_at=expires_at)
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)
                self.stats.evictions += 1

    def get_or_compute(
        self,
        key: K,
        factory: Callable[[], V],
        *,
        ttl: timedelta | None = None,
    ) -> V:
        existing = self.get(key)
        if existing is not None:
            return existing
        computed = factory()
        self.set(key, computed, ttl=ttl)
        return computed

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


__all__ = ["Cache", "CacheStats", "LruCache"]
