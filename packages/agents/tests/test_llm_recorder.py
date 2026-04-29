from __future__ import annotations

from decimal import Decimal

from qaforge_agents.llm.recorder import InMemoryRecorder
from qaforge_agents.llm.types import Tier, UsageRecord


def _record(prefix: str = "x") -> UsageRecord:
    now = UsageRecord.now_utc()
    return UsageRecord(
        provider="mock",
        model="mock-model",
        tier=Tier.MID,
        prompt_tokens=10,
        completion_tokens=20,
        usd_cost=Decimal("0.001"),
        latency_ms=42,
        started_at=now,
        finished_at=now,
        metadata={"prefix": prefix},
    )


def test_in_memory_recorder_appends() -> None:
    rec = InMemoryRecorder()
    rec.record(_record("a"))
    rec.record(_record("b"))
    assert [r.metadata["prefix"] for r in rec.records] == ["a", "b"]


def test_in_memory_recorder_reset_clears() -> None:
    rec = InMemoryRecorder()
    rec.record(_record())
    rec.reset()
    assert rec.records == []
