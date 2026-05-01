from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel

from aqao_agents.llm.client import LLMClient, StructuredOutputError
from aqao_agents.llm.providers.base import ProviderError
from aqao_agents.llm.providers.mock import MockProvider, MockTurn
from aqao_agents.llm.recorder import InMemoryRecorder
from aqao_agents.llm.types import LLMRequest, Message, ModelSpec, Role, Tier


def _request(**kwargs: object) -> LLMRequest:
    base: dict[str, object] = {
        "messages": [Message(role=Role.USER, content="ping")],
        "tier": Tier.MID,
    }
    base.update(kwargs)
    return LLMRequest.model_validate(base)


def _client(
    *,
    mock: MockProvider | None = None,
    tier_models: dict[Tier, list[ModelSpec]] | None = None,
    recorder: InMemoryRecorder | None = None,
) -> tuple[LLMClient, MockProvider, InMemoryRecorder]:
    provider = mock or MockProvider()
    rec = recorder or InMemoryRecorder()
    tiers = tier_models or {
        Tier.HIGH: [ModelSpec(provider="mock", model="mock-model")],
        Tier.MID: [ModelSpec(provider="mock", model="mock-model")],
        Tier.LOW: [ModelSpec(provider="mock", model="mock-model")],
    }
    client = LLMClient(
        providers={"mock": provider},
        recorder=rec,
        tier_models=tiers,
    )
    return client, provider, rec


@pytest.mark.asyncio
async def test_complete_returns_content_and_records_usage() -> None:
    provider = MockProvider([MockTurn(content="pong", prompt_tokens=10, completion_tokens=4)])
    client, _, recorder = _client(mock=provider)

    response = await client.complete(_request())

    assert response.content == "pong"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 4
    assert response.usage.provider == "mock"
    assert response.usage.usd_cost == Decimal("0")  # mock model is priced at zero
    assert recorder.records == [response.usage]


@pytest.mark.asyncio
async def test_tier_routes_to_first_candidate() -> None:
    primary = MockProvider([MockTurn(content="from-primary")])
    secondary = MockProvider()
    client = LLMClient(
        providers={"mock": primary, "mock2": secondary},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.MID: [
                ModelSpec(provider="mock", model="mock-model"),
                ModelSpec(provider="mock2", model="mock-model"),
            ]
        },
    )

    response = await client.complete(_request())
    assert response.content == "from-primary"
    assert len(secondary.calls) == 0


@pytest.mark.asyncio
async def test_transient_error_retries_same_candidate_then_succeeds() -> None:
    provider = MockProvider(
        [
            MockTurn(error=ProviderError("mock", "boom", transient=True)),
            MockTurn(content="recovered"),
        ]
    )
    client, _, recorder = _client(mock=provider)

    response = await client.complete(_request())
    assert response.content == "recovered"
    assert len(recorder.records) == 1


@pytest.mark.asyncio
async def test_non_transient_error_falls_over_to_next_candidate() -> None:
    primary = MockProvider([MockTurn(error=ProviderError("a", "nope", transient=False))])
    secondary = MockProvider([MockTurn(content="hello-from-secondary")])
    client = LLMClient(
        providers={"a": primary, "b": secondary},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.MID: [
                ModelSpec(provider="a", model="m"),
                ModelSpec(provider="b", model="m"),
            ]
        },
    )

    response = await client.complete(_request())
    assert response.content == "hello-from-secondary"
    assert response.usage.provider == "b"


@pytest.mark.asyncio
async def test_all_candidates_fail_raises_last_error() -> None:
    primary = MockProvider([MockTurn(error=ProviderError("a", "down", transient=False))])
    secondary = MockProvider([MockTurn(error=ProviderError("b", "also-down", transient=False))])
    client = LLMClient(
        providers={"a": primary, "b": secondary},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.MID: [
                ModelSpec(provider="a", model="m"),
                ModelSpec(provider="b", model="m"),
            ]
        },
    )

    with pytest.raises(ProviderError, match="also-down"):
        await client.complete(_request())


class _Plan(BaseModel):
    title: str
    steps: list[str]


@pytest.mark.asyncio
async def test_structured_output_validates_against_schema() -> None:
    payload = '{"title":"login flow","steps":["sign in","logout"]}'
    provider = MockProvider([MockTurn(content=payload)])
    client, _, _ = _client(mock=provider)

    response = await client.complete(_request(response_schema=_Plan))
    assert isinstance(response.structured, _Plan)
    assert response.structured.title == "login flow"


@pytest.mark.asyncio
async def test_structured_output_raises_on_invalid_json() -> None:
    provider = MockProvider([MockTurn(content="not-json")])
    client, _, _ = _client(mock=provider)
    with pytest.raises(StructuredOutputError, match="not valid JSON"):
        await client.complete(_request(response_schema=_Plan))


@pytest.mark.asyncio
async def test_structured_output_raises_on_schema_mismatch() -> None:
    provider = MockProvider([MockTurn(content='{"title":"x"}')])  # missing steps
    client, _, _ = _client(mock=provider)
    with pytest.raises(StructuredOutputError, match="failed schema validation"):
        await client.complete(_request(response_schema=_Plan))


@pytest.mark.asyncio
async def test_pricing_applies_for_known_model() -> None:
    provider = MockProvider([MockTurn(content="ok", prompt_tokens=10_000, completion_tokens=2_000)])
    client = LLMClient(
        providers={"anthropic": provider},
        recorder=InMemoryRecorder(),
        tier_models={Tier.MID: [ModelSpec(provider="anthropic", model="claude-sonnet-4-6")]},
    )

    response = await client.complete(_request())
    # 10k * $3/M + 2k * $15/M = 0.03 + 0.03 = 0.06
    assert response.usage.usd_cost == Decimal("0.06")
