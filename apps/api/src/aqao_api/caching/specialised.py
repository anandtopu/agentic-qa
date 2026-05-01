"""Specialised caches built on :class:`LruCache` — Epic 4.5.

Each wrapper picks a sensible key shape + default capacity for its
use case:

* :class:`EmbeddingCache` — ``sha256(model + ':' + text)`` is the
  cache key. Embeddings are pure functions of input so the hash is
  collision-safe even across model upgrades (model name participates
  in the hash).
* :class:`PlanReuseCache` — ``(workspace_id, requirement_hash)``.
  Two PRs that touch the same requirement share planner output;
  callers invalidate explicitly when the requirement is edited.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from aqao_api.caching.lru import LruCache


def _embedding_key(*, model: str, text: str) -> str:
    blob = f"{model}::{text}".encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass(slots=True)
class EmbeddingCache:
    """Content-addressed embedding cache."""

    inner: LruCache[str, list[float]]

    @classmethod
    def with_capacity(
        cls,
        *,
        capacity: int = 4096,
        ttl: timedelta | None = timedelta(days=7),
    ) -> EmbeddingCache:
        return cls(inner=LruCache(capacity=capacity, default_ttl=ttl))

    def get_or_compute(
        self,
        *,
        model: str,
        text: str,
        factory: Callable[[], list[float]],
    ) -> list[float]:
        return self.inner.get_or_compute(_embedding_key(model=model, text=text), factory)

    def get(self, *, model: str, text: str) -> list[float] | None:
        return self.inner.get(_embedding_key(model=model, text=text))

    def set(self, *, model: str, text: str, vector: list[float]) -> None:
        self.inner.set(_embedding_key(model=model, text=text), vector)


def _plan_key(*, workspace_id: UUID, requirement_hash: str) -> tuple[UUID, str]:
    return (workspace_id, requirement_hash)


@dataclass(slots=True)
class PlanReuseCache:
    """Re-use planner output for identical requirements within a workspace."""

    inner: LruCache[tuple[UUID, str], dict[str, Any]]

    @classmethod
    def with_capacity(
        cls,
        *,
        capacity: int = 512,
        ttl: timedelta | None = timedelta(hours=12),
    ) -> PlanReuseCache:
        return cls(inner=LruCache(capacity=capacity, default_ttl=ttl))

    def get(self, *, workspace_id: UUID, requirement_hash: str) -> dict[str, Any] | None:
        return self.inner.get(
            _plan_key(workspace_id=workspace_id, requirement_hash=requirement_hash)
        )

    def set(
        self,
        *,
        workspace_id: UUID,
        requirement_hash: str,
        plan: dict[str, Any],
    ) -> None:
        self.inner.set(
            _plan_key(workspace_id=workspace_id, requirement_hash=requirement_hash),
            plan,
        )

    def invalidate(self, *, workspace_id: UUID, requirement_hash: str) -> None:
        self.inner.invalidate(
            _plan_key(workspace_id=workspace_id, requirement_hash=requirement_hash)
        )


__all__ = ["EmbeddingCache", "PlanReuseCache"]
