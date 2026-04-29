from __future__ import annotations

from decimal import Decimal

import pytest

from qaforge_agents.llm.pricing import ModelPricing, default_pricing


def test_cost_zero_when_no_tokens() -> None:
    p = ModelPricing(input_per_mtok=Decimal("3"), output_per_mtok=Decimal("15"))
    assert p.cost_for(prompt_tokens=0, completion_tokens=0) == Decimal("0")


def test_cost_input_and_output_separately_billed() -> None:
    p = ModelPricing(input_per_mtok=Decimal("3"), output_per_mtok=Decimal("15"))
    # 1M input @ $3 + 1M output @ $15 = $18
    assert p.cost_for(prompt_tokens=1_000_000, completion_tokens=1_000_000) == Decimal("18")


def test_cached_tokens_default_to_ten_percent_of_input() -> None:
    p = ModelPricing(input_per_mtok=Decimal("10"), output_per_mtok=Decimal("0"))
    # 1M total input, of which 500k cached.
    # billable: 500k @ $10/M = $5; cached: 500k @ $1/M = $0.5; total $5.5
    cost = p.cost_for(prompt_tokens=1_000_000, completion_tokens=0, cached_prompt_tokens=500_000)
    assert cost == Decimal("5.5")


def test_cached_tokens_cannot_exceed_prompt_tokens() -> None:
    p = ModelPricing(input_per_mtok=Decimal("1"), output_per_mtok=Decimal("1"))
    with pytest.raises(ValueError, match="cached_prompt_tokens"):
        p.cost_for(prompt_tokens=10, completion_tokens=0, cached_prompt_tokens=11)


def test_default_pricing_covers_advertised_default_models() -> None:
    pricing = default_pricing()
    for spec in [
        ("anthropic", "claude-opus-4-7"),
        ("anthropic", "claude-sonnet-4-6"),
        ("anthropic", "claude-haiku-4-5"),
        ("openai", "gpt-5.1"),
        ("openai", "gpt-5.1-mini"),
    ]:
        assert spec in pricing, f"missing pricing for {spec}"


def test_default_pricing_cost_for_realistic_call() -> None:
    sonnet = default_pricing()[("anthropic", "claude-sonnet-4-6")]
    # 10k input + 2k output: 10000*3/1e6 + 2000*15/1e6 = $0.03 + $0.03 = $0.06
    cost = sonnet.cost_for(prompt_tokens=10_000, completion_tokens=2_000)
    assert cost == Decimal("0.06")
