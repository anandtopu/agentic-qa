"""Reliability-pattern tests — Epic 4.3.

Covers all four primitives (CircuitBreaker / Bulkhead / DLQ /
Idempotency), plus the AC-verification chaos test:

> Chaos test (provider 500s for 5 min) keeps platform operational
> with degraded mode.

Modeled here as: with a CircuitBreaker wrapping a `_flaky_provider`
that 500s for 5 minutes, the platform's classifier-equivalent
fallback continues serving requests via the heuristic path while the
breaker is open, and recovers once the provider does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aqao_api.reliability import (
    BreakerOpen,
    BreakerState,
    Bulkhead,
    BulkheadFull,
    BulkheadRegistry,
    CircuitBreaker,
    DeadLetter,
    IdempotencyConflict,
    InMemoryDeadLetterQueue,
    InMemoryIdempotencyStore,
)

# ---------------------------------------------------------------- circuit breaker


def test_breaker_starts_closed_and_passes_calls_through() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=3)
    assert cb.call(lambda: 42) == 42
    assert cb.state is BreakerState.CLOSED


def test_breaker_opens_after_failure_threshold_consecutive_failures() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=3)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cb.state is BreakerState.OPEN
    assert cb.opened_at is not None


def test_open_breaker_short_circuits_subsequent_calls() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cb.state is BreakerState.OPEN
    with pytest.raises(BreakerOpen):
        cb.call(lambda: 99)


def test_breaker_recovers_via_half_open_after_timeout() -> None:
    cb = CircuitBreaker(
        name="test",
        failure_threshold=1,
        recovery_timeout=timedelta(seconds=1),
    )
    base = datetime(2026, 5, 1, tzinfo=UTC)

    with pytest.raises(RuntimeError):
        cb.call(
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            now=base,
        )
    assert cb.state is BreakerState.OPEN

    later = base + timedelta(seconds=2)
    # First call after recovery_timeout transitions to half-open and
    # tries the trial. Success -> closes the breaker.
    assert cb.call(lambda: "ok", now=later) == "ok"
    assert cb.state is BreakerState.CLOSED


def test_half_open_failure_re_opens_breaker_immediately() -> None:
    cb = CircuitBreaker(
        name="test",
        failure_threshold=1,
        recovery_timeout=timedelta(seconds=1),
    )
    base = datetime(2026, 5, 1, tzinfo=UTC)

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")), now=base)

    later = base + timedelta(seconds=2)
    with pytest.raises(RuntimeError):
        cb.call(
            lambda: (_ for _ in ()).throw(RuntimeError("still broken")),
            now=later,
        )
    assert cb.state is BreakerState.OPEN


def test_breaker_resets_consecutive_failures_on_success() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=3)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    cb.call(lambda: "ok")
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    # Two non-consecutive failures stay below the 3-threshold.
    assert cb.state is BreakerState.CLOSED


@pytest.mark.asyncio
async def test_breaker_async_call_path() -> None:
    cb = CircuitBreaker(name="async", failure_threshold=2)

    async def good() -> int:
        return 7

    async def bad() -> int:
        raise RuntimeError("nope")

    assert await cb.acall(good) == 7
    with pytest.raises(RuntimeError):
        await cb.acall(bad)
    with pytest.raises(RuntimeError):
        await cb.acall(bad)
    assert cb.state is BreakerState.OPEN


# ---------------------------------------------------------------- chaos AC


def test_chaos_provider_500_for_5_min_keeps_platform_in_degraded_mode() -> None:
    """AC: provider 500s for 5 min -> platform stays operational via
    degraded fallback. We stand in for "platform" with a function
    that prefers the LLM result (via the breaker) but falls back to
    a deterministic heuristic on `BreakerOpen`.
    """
    cb = CircuitBreaker(
        name="llm",
        failure_threshold=3,
        recovery_timeout=timedelta(minutes=5),
    )
    base = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    # Provider 500s for 5 minutes, then recovers.
    def provider(now: datetime) -> str:
        if now < base + timedelta(minutes=5):
            raise RuntimeError("provider 500")
        return "llm-answer"

    def classify(now: datetime) -> str:
        try:
            return cb.call(lambda: provider(now), now=now)
        except (RuntimeError, BreakerOpen):
            return "heuristic-answer"

    # Tick once a second for 5 minutes.
    answers: list[str] = []
    for offset in range(0, 5 * 60, 30):
        answers.append(classify(base + timedelta(seconds=offset)))

    # Every classify call succeeded — the platform never raised to the user.
    assert len(answers) > 0
    # While the breaker was open most of those answers are heuristic.
    assert "heuristic-answer" in answers
    # And after the provider recovers + recovery_timeout elapses,
    # the breaker closes and the LLM answer flows again.
    recovered = classify(base + timedelta(minutes=10))
    assert recovered == "llm-answer"
    assert cb.state is BreakerState.CLOSED


# ---------------------------------------------------------------- bulkhead


def test_bulkhead_allows_up_to_capacity_then_raises() -> None:
    bh = Bulkhead(name="ws-1", capacity=2)
    with bh.acquire(), bh.acquire():
        assert bh.in_use == 2
        with pytest.raises(BulkheadFull), bh.acquire():
            pass


def test_bulkhead_releases_slot_after_context_exits() -> None:
    bh = Bulkhead(name="ws-1", capacity=1)
    with bh.acquire():
        pass
    assert bh.in_use == 0
    # Slot is reclaimed — second acquire succeeds.
    with bh.acquire():
        pass


def test_bulkhead_releases_slot_even_on_exception() -> None:
    bh = Bulkhead(name="ws-1", capacity=1)
    with pytest.raises(ValueError), bh.acquire():
        raise ValueError("inside")
    assert bh.in_use == 0


def test_bulkhead_registry_creates_per_key_bulkheads_lazily() -> None:
    registry = BulkheadRegistry(default_capacity=4)
    a = registry.for_key("workspace-a")
    b = registry.for_key("workspace-b")
    again = registry.for_key("workspace-a")
    assert a is again
    assert a is not b
    assert a.capacity == 4


# ---------------------------------------------------------------- DLQ


def test_dlq_append_and_drain() -> None:
    q = InMemoryDeadLetterQueue()
    q.append_failure(
        task_id="t-1",
        workspace_id="ws-1",
        error_message="boom",
    )
    q.append_failure(
        task_id="t-2",
        workspace_id="ws-1",
        error_message="kaboom",
        attempts=3,
    )
    assert q.depth() == 2
    drained = q.drain(limit=1)
    assert len(drained) == 1
    assert drained[0].task_id == "t-1"
    assert q.depth() == 1


def test_dlq_drain_more_than_present_returns_what_exists() -> None:
    q = InMemoryDeadLetterQueue()
    q.append_failure(task_id="t-1", workspace_id="ws-1", error_message="x")
    drained = q.drain(limit=100)
    assert len(drained) == 1
    assert q.depth() == 0


def test_dlq_letter_carries_payload() -> None:
    q = InMemoryDeadLetterQueue()
    letter = q.append_failure(
        task_id="t-1",
        workspace_id="ws-1",
        error_message="boom",
        payload={"step": "classify"},
    )
    assert isinstance(letter, DeadLetter)
    assert letter.payload["step"] == "classify"


# ---------------------------------------------------------------- idempotency


def test_idempotency_first_write_wins_and_returns_was_new_true() -> None:
    store = InMemoryIdempotencyStore()
    tenant = uuid.uuid4()
    response, was_new = store.remember(
        tenant_id=tenant,
        key="key-1",
        body={"a": 1},
        response={"id": "x"},
        ttl=timedelta(hours=1),
    )
    assert was_new is True
    assert response == {"id": "x"}


def test_idempotency_retry_with_same_body_returns_cached_response() -> None:
    store = InMemoryIdempotencyStore()
    tenant = uuid.uuid4()
    store.remember(
        tenant_id=tenant,
        key="key-1",
        body={"a": 1},
        response={"id": "x"},
        ttl=timedelta(hours=1),
    )
    cached, was_new = store.remember(
        tenant_id=tenant,
        key="key-1",
        body={"a": 1},
        response={"id": "y"},  # caller proposed a different response
        ttl=timedelta(hours=1),
    )
    assert was_new is False
    # First-write-wins: cached response is preserved.
    assert cached == {"id": "x"}


def test_idempotency_retry_with_different_body_raises() -> None:
    store = InMemoryIdempotencyStore()
    tenant = uuid.uuid4()
    store.remember(
        tenant_id=tenant,
        key="key-1",
        body={"a": 1},
        response={"id": "x"},
        ttl=timedelta(hours=1),
    )
    with pytest.raises(IdempotencyConflict):
        store.remember(
            tenant_id=tenant,
            key="key-1",
            body={"a": 2},  # different body!
            response={"id": "y"},
            ttl=timedelta(hours=1),
        )


def test_idempotency_expired_record_is_replaced_silently() -> None:
    store = InMemoryIdempotencyStore()
    tenant = uuid.uuid4()
    base = datetime(2026, 5, 1, tzinfo=UTC)
    store.remember(
        tenant_id=tenant,
        key="key-1",
        body={"a": 1},
        response={"id": "x"},
        ttl=timedelta(hours=1),
        now=base,
    )
    later = base + timedelta(hours=2)
    cached, was_new = store.remember(
        tenant_id=tenant,
        key="key-1",
        body={"a": 1},
        response={"id": "z"},
        ttl=timedelta(hours=1),
        now=later,
    )
    assert was_new is True
    assert cached == {"id": "z"}


def test_idempotency_keys_are_per_tenant() -> None:
    store = InMemoryIdempotencyStore()
    a, b = uuid.uuid4(), uuid.uuid4()
    store.remember(
        tenant_id=a,
        key="key-1",
        body={"a": 1},
        response={"id": "from-a"},
        ttl=timedelta(hours=1),
    )
    cached, was_new = store.remember(
        tenant_id=b,
        key="key-1",
        body={"a": 999},
        response={"id": "from-b"},
        ttl=timedelta(hours=1),
    )
    assert was_new is True
    assert cached == {"id": "from-b"}


def test_idempotency_fetch_returns_none_for_unknown_key() -> None:
    store = InMemoryIdempotencyStore()
    assert store.fetch(tenant_id=uuid.uuid4(), key="nope") is None
