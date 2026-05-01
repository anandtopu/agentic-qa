"""Caching primitives — Epic 4.5.

Three caches the platform reaches for to hit PRD §14.5 budgets:

* :class:`LruCache` — process-local LRU with TTL, used for hot-path
  HTTP responses and prompt template lookups.
* :class:`EmbeddingCache` — content-addressed cache keyed by
  ``sha256(model + text)``; embeddings are pure functions of input
  so the hash is the cache key.
* :class:`PlanReuseCache` — keyed by ``(workspace, requirement_hash)``
  so two PRs touching the same requirement share the planner output
  unless the upstream code path explicitly invalidates.

All three share a thread-safe :class:`Cache` Protocol so a Redis impl
drops in by satisfying the same interface.
"""

from aqao_api.caching.lru import Cache, CacheStats, LruCache
from aqao_api.caching.specialised import EmbeddingCache, PlanReuseCache

__all__ = [
    "Cache",
    "CacheStats",
    "EmbeddingCache",
    "LruCache",
    "PlanReuseCache",
]
