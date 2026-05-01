"""Idempotency-key store — Epic 4.3.

First-write-wins cache keyed by ``(tenant, key)``. A repeated POST
with the same idempotency key returns the cached response instead of
double-creating. Body-hash mismatch on a re-used key raises
:class:`IdempotencyConflict` (HTTP 409 territory).
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID


class IdempotencyConflict(RuntimeError):  # noqa: N818 - public name predates rule
    """A second request with the same key had a different body hash."""

    def __init__(self, key: str, expected_hash: str, observed_hash: str) -> None:
        super().__init__(
            f"idempotency-key {key!r} body hash mismatch: "
            f"first={expected_hash}, retry={observed_hash}"
        )
        self.key = key
        self.expected_hash = expected_hash
        self.observed_hash = observed_hash


@dataclass(slots=True, frozen=True)
class IdempotencyRecord:
    tenant_id: UUID
    key: str
    body_hash: str
    response: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class IdempotencyStore(Protocol):
    """Required surface — production deployments back this with
    Postgres or Redis; tests use the in-memory reference impl."""

    def remember(
        self,
        *,
        tenant_id: UUID,
        key: str,
        body: Mapping[str, Any],
        response: Mapping[str, Any],
        ttl: timedelta,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], bool]: ...

    def fetch(
        self,
        *,
        tenant_id: UUID,
        key: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None: ...


def _hash_body(body: Mapping[str, Any]) -> str:
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass(slots=True)
class InMemoryIdempotencyStore:
    """Thread-safe dict-backed store for tests + dev."""

    records: dict[tuple[UUID, str], IdempotencyRecord] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def remember(
        self,
        *,
        tenant_id: UUID,
        key: str,
        body: Mapping[str, Any],
        response: Mapping[str, Any],
        ttl: timedelta,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Either record the response (first call) or return the cached
        one (retry).

        Returns ``(response, was_new)``. Raises
        :class:`IdempotencyConflict` if the body hash differs from
        the first call.
        """
        moment = now or datetime.now(UTC)
        body_hash = _hash_body(body)
        composite_key = (tenant_id, key)
        with self._lock:
            existing = self.records.get(composite_key)
            if existing is not None and existing.expires_at > moment:
                if existing.body_hash != body_hash:
                    raise IdempotencyConflict(
                        key=key,
                        expected_hash=existing.body_hash,
                        observed_hash=body_hash,
                    )
                return dict(existing.response), False

            record = IdempotencyRecord(
                tenant_id=tenant_id,
                key=key,
                body_hash=body_hash,
                response=dict(response),
                created_at=moment,
                expires_at=moment + ttl,
            )
            self.records[composite_key] = record
            return dict(response), True

    def fetch(
        self,
        *,
        tenant_id: UUID,
        key: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        moment = now or datetime.now(UTC)
        with self._lock:
            existing = self.records.get((tenant_id, key))
            if existing is None or existing.expires_at <= moment:
                return None
            return dict(existing.response)


__all__ = [
    "IdempotencyConflict",
    "IdempotencyRecord",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
]
