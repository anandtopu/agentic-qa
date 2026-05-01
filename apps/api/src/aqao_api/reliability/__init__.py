"""Reliability patterns — Epic 4.3.

Four primitives the platform reaches for under load:

* :class:`CircuitBreaker` — wraps a remote call (LLM provider, etc.)
  and short-circuits to a degraded mode after consecutive failures.
* :class:`Bulkhead` — per-workspace concurrency cap so one tenant's
  burst can't starve another tenant.
* :class:`DeadLetterQueue` — in-memory + Protocol seam for failed
  agent tasks. Production deployments swap a Redis / SQS impl.
* :class:`IdempotencyStore` — first-write-wins cache keyed by
  ``(tenant, key)`` so retries don't double-create.
"""

from aqao_api.reliability.bulkhead import (
    Bulkhead,
    BulkheadFull,
    BulkheadRegistry,
)
from aqao_api.reliability.circuit_breaker import (
    BreakerOpen,
    BreakerState,
    CircuitBreaker,
)
from aqao_api.reliability.dlq import (
    DeadLetter,
    DeadLetterQueue,
    InMemoryDeadLetterQueue,
)
from aqao_api.reliability.idempotency import (
    IdempotencyConflict,
    IdempotencyStore,
    InMemoryIdempotencyStore,
)

__all__ = [
    "BreakerOpen",
    "BreakerState",
    "Bulkhead",
    "BulkheadFull",
    "BulkheadRegistry",
    "CircuitBreaker",
    "DeadLetter",
    "DeadLetterQueue",
    "IdempotencyConflict",
    "IdempotencyStore",
    "InMemoryDeadLetterQueue",
    "InMemoryIdempotencyStore",
]
