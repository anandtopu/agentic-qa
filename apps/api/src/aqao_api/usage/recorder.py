"""Buffered DB-backed usage recorder."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from aqao_agents.llm.types import UsageRecord
from aqao_api.db.models import UsageRecordRow


@dataclass(slots=True)
class DbUsageRecorder:
    """Implements :class:`aqao_agents.llm.recorder.UsageRecorder`.

    Records are buffered in-memory during a request and flushed in
    one shot via :meth:`flush`. The flush call is the only place that
    touches the DB, so the recorder itself is decoupled from the
    request's session lifetime.
    """

    records: list[UsageRecord] = field(default_factory=list)

    def record(self, usage: UsageRecord) -> None:
        self.records.append(usage)

    def reset(self) -> None:
        self.records.clear()

    def flush(
        self,
        *,
        session: Session,
        tenant_id: UUID,
        workspace_id: UUID | None,
        test_run_id: UUID | None,
        agent_name: str,
    ) -> int:
        """Write every buffered record as one ``usage_records`` row.

        Returns the number of rows written. Clears the in-memory buffer
        on success so the same recorder can be reused.
        """
        if not self.records:
            return 0

        for usage in self.records:
            row = UsageRecordRow(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                test_run_id=test_run_id,
                agent_name=agent_name,
                provider=usage.provider,
                model=usage.model,
                tier=usage.tier.value,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cached_prompt_tokens=usage.cached_prompt_tokens,
                usd_cost=usage.usd_cost,
                latency_ms=usage.latency_ms,
                correlation_id=usage.correlation_id,
                metadata_json=dict(usage.metadata),
            )
            session.add(row)
        written = len(self.records)
        session.flush()
        self.records.clear()
        return written
