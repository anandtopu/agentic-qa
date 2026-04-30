"""Unit tests for the combined FailureClassifierAgent — Story 1.7."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from qaforge_agents.classifier import (
    FailureCategory,
    FailureClassifierAgent,
    FailureSignal,
    HeuristicClassifier,
    LlmClassifier,
)
from qaforge_agents.classifier.schema import ClassificationSource
from qaforge_agents.llm.client import LLMClient
from qaforge_agents.llm.providers.mock import MockProvider, MockTurn
from qaforge_agents.llm.recorder import InMemoryRecorder
from qaforge_agents.llm.types import ModelSpec, Tier


def _llm_client(*responses: str) -> LLMClient:
    turns = [MockTurn(content=r) for r in responses]
    return LLMClient(
        providers={"mock": MockProvider(turns)},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.MID: [ModelSpec(provider="mock", model="mock-model")],
            Tier.HIGH: [ModelSpec(provider="mock", model="mock-model")],
            Tier.LOW: [ModelSpec(provider="mock", model="mock-model")],
        },
    )


def _llm_payload(category: str, *, confidence: float = 0.7) -> str:
    return json.dumps(
        {
            "category": category,
            "confidence": confidence,
            "reasoning": f"Mock LLM said {category}.",
            "suggested_fix": None,
        }
    )


@pytest.mark.asyncio
async def test_heuristic_handles_recognised_signal_without_llm() -> None:
    agent = FailureClassifierAgent(
        llm_classifier=LlmClassifier(_llm_client()),  # no scripted turns needed
        heuristic=HeuristicClassifier(),
    )
    out = await agent.classify_signals(
        [
            FailureSignal(
                signal_id="s1",
                http_status_code=503,
                error_message="upstream blew up",
            )
        ]
    )
    assert out.heuristic_hits == 1
    assert out.llm_hits == 0
    assert out.usage_records == []
    assert out.classifications[0].classified_by is ClassificationSource.HEURISTIC


@pytest.mark.asyncio
async def test_falls_through_to_llm_when_heuristic_misses() -> None:
    agent = FailureClassifierAgent(
        llm_classifier=LlmClassifier(_llm_client(_llm_payload("flaky_test", confidence=0.6))),
    )
    out = await agent.classify_signals(
        [
            FailureSignal(
                signal_id="s1",
                error_message="unrecognised but probably intermittent",
            )
        ]
    )
    assert out.heuristic_hits == 0
    assert out.llm_hits == 1
    assert out.classifications[0].category is FailureCategory.FLAKY_TEST
    assert out.classifications[0].classified_by is ClassificationSource.LLM
    assert len(out.usage_records) == 1


@pytest.mark.asyncio
async def test_mixed_batch_uses_both_paths() -> None:
    agent = FailureClassifierAgent(
        llm_classifier=LlmClassifier(_llm_client(_llm_payload("test_issue"))),
    )
    out = await agent.classify_signals(
        [
            FailureSignal(
                signal_id="known",
                http_status_code=503,
                error_message="x",
            ),
            FailureSignal(
                signal_id="unknown",
                error_message="something subtle and novel",
            ),
        ]
    )
    assert out.heuristic_hits == 1
    assert out.llm_hits == 1
    assert out.heuristic_ratio == Decimal("0.50")


def test_category_summary_groups_counts() -> None:
    classifications = [
        _stub("a", FailureCategory.FLAKY_TEST),
        _stub("b", FailureCategory.FLAKY_TEST),
        _stub("c", FailureCategory.PRODUCT_DEFECT),
    ]
    assert FailureClassifierAgent.category_summary(classifications) == {
        "flaky_test": 2,
        "product_defect": 1,
    }


def test_source_summary_initialises_both_keys() -> None:
    assert FailureClassifierAgent.source_summary([]) == {
        "heuristic": 0,
        "llm": 0,
    }


def _stub(signal_id: str, category: FailureCategory):
    from qaforge_agents.classifier.schema import Classification

    return Classification(
        signal_id=signal_id,
        category=category,
        confidence=Decimal("0.5"),
        classified_by=ClassificationSource.HEURISTIC,
        reasoning="stub",
    )
