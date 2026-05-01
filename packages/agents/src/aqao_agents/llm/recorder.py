"""Usage recorders.

Phase 0 ships in-memory and structlog-backed recorders. Phase 1's Story
1.x adds a ``DatabaseRecorder`` that writes to the ``usage_records`` table
(PRD §12) — both shipped recorders implement the same Protocol so the
swap is local.
"""

from __future__ import annotations

from typing import Protocol

import structlog

from aqao_agents.llm.types import UsageRecord


class UsageRecorder(Protocol):
    """Sink for usage telemetry. Must not raise — recording is best-effort."""

    def record(self, usage: UsageRecord) -> None: ...


class InMemoryRecorder:
    """Test/in-process recorder. Holds records in a list."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def record(self, usage: UsageRecord) -> None:
        self.records.append(usage)

    def reset(self) -> None:
        self.records.clear()


class StructLogRecorder:
    """Emits each usage record as a structured log line.

    Useful in dev and as a belt-and-braces sink in prod where the DB
    recorder is the primary path.
    """

    def __init__(self, logger_name: str = "aqao_agents.llm.usage") -> None:
        self._log = structlog.get_logger(logger_name)

    def record(self, usage: UsageRecord) -> None:
        self._log.info(
            "llm.usage",
            provider=usage.provider,
            model=usage.model,
            tier=usage.tier.value,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cached_prompt_tokens=usage.cached_prompt_tokens,
            usd_cost=str(usage.usd_cost),
            latency_ms=usage.latency_ms,
            correlation_id=usage.correlation_id,
            workspace_id=str(usage.workspace_id) if usage.workspace_id else None,
            **usage.metadata,
        )
