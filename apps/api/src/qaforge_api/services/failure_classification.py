"""FailureClassificationService — Story 1.7.

Persists the agent's output to ``failure_classifications`` and audits.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_agents.classifier import (
    Classification,
    FailureClassifierAgent,
    FailureSignal,
)
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    ClassifiedBy,
    FailureCategory,
    FailureClassification,
    TestRun,
)
from qaforge_api.db.models.failure_classification import (
    ClassifiedBy as DbClassifiedBy,
)
from qaforge_api.db.models.failure_classification import (
    FailureCategory as DbFailureCategory,
)
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError


@dataclass(slots=True)
class FailureClassificationOutput:
    test_run_id: UUID
    classifications: list[FailureClassification]
    heuristic_ratio: Decimal
    llm_call_count: int
    total_usd_cost_cents: int


class FailureClassificationService:
    def __init__(self, session: Session, agent: FailureClassifierAgent) -> None:
        self._session = session
        self._agent = agent
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def list_for_run(self, test_run_id: UUID) -> Sequence[FailureClassification]:
        stmt = (
            select(FailureClassification)
            .where(FailureClassification.test_run_id == test_run_id)
            .order_by(FailureClassification.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    # --- mutations --------------------------------------------------------------

    async def classify(
        self,
        *,
        test_run_id: UUID,
        signals: Sequence[FailureSignal],
        context: RequestContext,
    ) -> FailureClassificationOutput:
        run = self._session.get(TestRun, test_run_id)
        if run is None:
            raise ResourceNotFoundError("test_run", test_run_id)

        result = await self._agent.classify_signals(signals)

        for c in result.classifications:
            row = FailureClassification(
                tenant_id=context.tenant_id,
                test_run_id=run.id,
                signal_id=c.signal_id,
                category=DbFailureCategory(c.category.value),
                confidence=c.confidence,
                classified_by=DbClassifiedBy(c.classified_by.value),
                rule=c.rule,
                reasoning=c.reasoning,
                suggested_fix=c.suggested_fix,
                raw_signal=_signal_to_payload(signals, c),
                model=c.model,
                prompt_version=c.prompt_version,
            )
            self._session.add(row)
        self._session.flush()

        total_cents = sum(round(float(u.usd_cost) * 100) for u in result.usage_records)
        self._audit.record(
            context=context,
            action="failure_classifications.recorded",
            resource_type="test_run",
            resource_id=run.id,
            payload={
                "total_signals": len(signals),
                "category_summary": FailureClassifierAgent.category_summary(result.classifications),
                "source_summary": FailureClassifierAgent.source_summary(result.classifications),
                "heuristic_ratio": str(result.heuristic_ratio),
                "llm_call_count": result.llm_hits,
                "usd_cost_cents": total_cents,
            },
        )

        rows = list(
            self._session.scalars(
                select(FailureClassification)
                .where(FailureClassification.test_run_id == run.id)
                .order_by(FailureClassification.created_at.asc())
            ).all()
        )
        return FailureClassificationOutput(
            test_run_id=run.id,
            classifications=rows,
            heuristic_ratio=result.heuristic_ratio,
            llm_call_count=result.llm_hits,
            total_usd_cost_cents=total_cents,
        )


def _signal_to_payload(
    signals: Sequence[FailureSignal], classification: Classification
) -> dict[str, object]:
    for signal in signals:
        if signal.signal_id == classification.signal_id:
            return signal.model_dump(mode="json")
    return {}


# Re-export for convenience: services/__init__ exports these as the
# Control-Plane-facing names.
__all__ = [
    "ClassifiedBy",
    "FailureCategory",
    "FailureClassificationOutput",
    "FailureClassificationService",
]
