"""Unit tests for DbUsageRecorder buffering — Story 2.5.1.

The DB-flush path is exercised under integration (real Postgres);
here we only verify the in-memory buffer + flush interaction with a
stub session that records the rows it sees.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from aqao_agents.llm.types import Tier, UsageRecord
from aqao_api.usage import DbUsageRecorder


@dataclass(slots=True)
class _StubSession:
    added: list[Any] = field(default_factory=list)
    flush_calls: int = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_calls += 1


def _usage(amount: str = "0.06") -> UsageRecord:
    now = datetime.now(UTC)
    return UsageRecord(
        provider="anthropic",
        model="claude-sonnet-4-6",
        tier=Tier.MID,
        prompt_tokens=10_000,
        completion_tokens=2_000,
        usd_cost=Decimal(amount),
        latency_ms=420,
        started_at=now,
        finished_at=now,
        metadata={"agent": "planner"},
    )


def test_recorder_starts_empty() -> None:
    rec = DbUsageRecorder()
    assert rec.records == []


def test_record_appends() -> None:
    rec = DbUsageRecorder()
    rec.record(_usage())
    rec.record(_usage("0.12"))
    assert len(rec.records) == 2


def test_reset_clears() -> None:
    rec = DbUsageRecorder()
    rec.record(_usage())
    rec.reset()
    assert rec.records == []


def test_flush_writes_rows_and_clears_buffer() -> None:
    rec = DbUsageRecorder()
    rec.record(_usage("0.05"))
    rec.record(_usage("0.07"))
    session = _StubSession()
    written = rec.flush(
        session=session,  # type: ignore[arg-type]
        tenant_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        test_run_id=uuid.uuid4(),
        agent_name="planner",
    )
    assert written == 2
    assert len(session.added) == 2
    assert session.flush_calls == 1
    assert rec.records == []


def test_flush_empty_buffer_is_noop() -> None:
    rec = DbUsageRecorder()
    session = _StubSession()
    written = rec.flush(
        session=session,  # type: ignore[arg-type]
        tenant_id=uuid.uuid4(),
        workspace_id=None,
        test_run_id=None,
        agent_name="planner",
    )
    assert written == 0
    assert session.added == []
    assert session.flush_calls == 0
