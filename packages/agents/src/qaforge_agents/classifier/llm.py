"""LLM classifier — Story 1.7.2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from qaforge_agents.classifier.prompt import (
    PROMPT_VERSION,
    SYSTEM,
    build_user_prompt,
)
from qaforge_agents.classifier.schema import (
    Classification,
    ClassificationSource,
    FailureCategory,
    FailureSignal,
)
from qaforge_agents.llm.client import LLMClient, StructuredOutputError
from qaforge_agents.llm.types import LLMRequest, Message, Role, Tier, UsageRecord


class _LlmOutput(BaseModel):
    """Schema the LLM is asked to fill — narrow on purpose."""

    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    reasoning: str = Field(min_length=1, max_length=4_000)
    suggested_fix: str | None = Field(default=None, max_length=2_000)


@dataclass(slots=True)
class LlmClassification:
    classification: Classification
    usage: UsageRecord


class LlmClassifier:
    """Phase 1 LLM-backed classifier (MID tier — quality matters but
    we expect to be invoked frequently).
    """

    def __init__(self, llm: LLMClient, *, tier: Tier = Tier.MID) -> None:
        self._llm = llm
        self._tier = tier

    async def classify(self, signal: FailureSignal) -> LlmClassification:
        schema_json = json.dumps(_LlmOutput.model_json_schema(), indent=2, sort_keys=True)
        request = LLMRequest(
            messages=[
                Message(role=Role.SYSTEM, content=SYSTEM),
                Message(
                    role=Role.USER,
                    content=build_user_prompt(signal=signal, response_schema_json=schema_json),
                ),
            ],
            tier=self._tier,
            response_schema=_LlmOutput,
            metadata={
                "agent": "failure_classifier",
                "prompt_version": PROMPT_VERSION,
                "signal_id": signal.signal_id,
            },
        )

        response = await self._llm.complete(request)
        if not isinstance(response.structured, _LlmOutput):
            raise StructuredOutputError("classifier LLM response was not an _LlmOutput")
        out: _LlmOutput = response.structured

        classification = Classification(
            signal_id=signal.signal_id,
            category=out.category,
            confidence=out.confidence,
            classified_by=ClassificationSource.LLM,
            rule=None,
            reasoning=out.reasoning,
            suggested_fix=out.suggested_fix,
            model=response.usage.model,
            prompt_version=PROMPT_VERSION,
        )
        return LlmClassification(classification=classification, usage=response.usage)
