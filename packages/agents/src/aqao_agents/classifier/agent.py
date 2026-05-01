"""FailureClassifierAgent — heuristic-then-LLM combined classifier.

Story 1.7 ties the two stages together. The agent is the only part the
Control Plane talks to: input is a list of :class:`FailureSignal`,
output is one :class:`Classification` per signal plus the aggregate
usage cost (zero when the heuristic handled it; positive when the LLM
did).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from aqao_agents.classifier.heuristic import HeuristicClassifier
from aqao_agents.classifier.llm import LlmClassifier
from aqao_agents.classifier.schema import (
    Classification,
    ClassificationSource,
    FailureSignal,
)
from aqao_agents.llm.types import UsageRecord


@dataclass(slots=True)
class FailureClassifierOutput:
    classifications: list[Classification]
    usage_records: list[UsageRecord] = field(default_factory=list)
    heuristic_hits: int = 0
    llm_hits: int = 0

    @property
    def total(self) -> int:
        return len(self.classifications)

    @property
    def heuristic_ratio(self) -> Decimal:
        """Proportion classified pre-LLM. Story 1.7.1 AC target: ≥0.30."""
        if not self.classifications:
            return Decimal("0")
        return (Decimal(self.heuristic_hits) / Decimal(self.total)).quantize(Decimal("0.01"))


class FailureClassifierAgent:
    def __init__(
        self,
        *,
        llm_classifier: LlmClassifier,
        heuristic: HeuristicClassifier | None = None,
    ) -> None:
        self._heuristic = heuristic or HeuristicClassifier()
        self._llm = llm_classifier

    async def classify_signals(self, signals: Sequence[FailureSignal]) -> FailureClassifierOutput:
        classifications: list[Classification] = []
        usage_records: list[UsageRecord] = []
        heuristic_hits = 0
        llm_hits = 0

        for signal in signals:
            heuristic_class = self._heuristic.classify_to_classification(signal)
            if heuristic_class is not None:
                classifications.append(heuristic_class)
                heuristic_hits += 1
                continue

            llm_out = await self._llm.classify(signal)
            classifications.append(llm_out.classification)
            usage_records.append(llm_out.usage)
            llm_hits += 1

        return FailureClassifierOutput(
            classifications=classifications,
            usage_records=usage_records,
            heuristic_hits=heuristic_hits,
            llm_hits=llm_hits,
        )

    @staticmethod
    def category_summary(
        classifications: Sequence[Classification],
    ) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in classifications:
            out[c.category.value] = out.get(c.category.value, 0) + 1
        return out

    @staticmethod
    def source_summary(
        classifications: Sequence[Classification],
    ) -> dict[str, int]:
        out: dict[str, int] = {
            ClassificationSource.HEURISTIC.value: 0,
            ClassificationSource.LLM.value: 0,
        }
        for c in classifications:
            out[c.classified_by.value] += 1
        return out
