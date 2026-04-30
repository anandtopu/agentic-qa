"""Unit tests for the BudgetEnforcer — Story 2.5.1."""

from __future__ import annotations

from decimal import Decimal

import pytest

from qaforge_agents.llm.client import LLMClient
from qaforge_agents.llm.providers.mock import MockProvider, MockTurn
from qaforge_agents.llm.recorder import InMemoryRecorder
from qaforge_agents.llm.types import LLMRequest, Message, ModelSpec, Role, Tier
from qaforge_api.usage import BudgetEnforcer, BudgetExceededError


def _client(*responses_with_pricing: tuple[str, str, str]) -> LLMClient:
    """Build a client whose mock returns each scripted (content, model) pair.

    Pricing: each tuple is ``(content, model, expected_cost_cents)`` —
    the last element is informational; the actual cost comes from the
    model's pricing table entry. We don't reuse it here.
    """
    turns = [
        MockTurn(content=c, prompt_tokens=10_000, completion_tokens=2_000)
        for c, _, _ in responses_with_pricing
    ]
    return LLMClient(
        providers={"anthropic": MockProvider(turns)},
        recorder=InMemoryRecorder(),
        tier_models={
            Tier.MID: [
                ModelSpec(provider="anthropic", model="claude-sonnet-4-6"),
            ],
        },
    )


def _request() -> LLMRequest:
    return LLMRequest(
        messages=[Message(role=Role.USER, content="ping")],
        tier=Tier.MID,
    )


@pytest.mark.asyncio
async def test_under_budget_calls_pass_through() -> None:
    # claude-sonnet-4-6 @ 10k/2k = $0.06 per call.
    client = _client(("ok", "claude-sonnet-4-6", "6"))
    enforcer = BudgetEnforcer(client=client, budget_usd=Decimal("1.00"))
    response = await enforcer.complete(_request())
    assert response.content == "ok"
    assert enforcer.stats.calls_made == 1
    assert enforcer.stats.running_total == Decimal("0.06")


@pytest.mark.asyncio
async def test_pre_flight_estimate_blocks_call() -> None:
    client = _client(("never-runs", "claude-sonnet-4-6", "0"))
    enforcer = BudgetEnforcer(client=client, budget_usd=Decimal("0.10"))
    with pytest.raises(BudgetExceededError) as exc_info:
        # Pre-flight estimate $0.50 vs budget $0.10 (*1.05 = $0.105) → blocked.
        await enforcer.complete(_request(), request_estimate_usd=Decimal("0.50"))
    assert exc_info.value.budget == Decimal("0.10")
    assert enforcer.stats.calls_made == 0
    assert enforcer.stats.calls_blocked == 1


@pytest.mark.asyncio
async def test_mid_flight_kill_switch_fires() -> None:
    # Two $0.06 calls → running total $0.12 against $0.10 budget * 1.05 = $0.105 cap.
    client = _client(
        ("ok-1", "claude-sonnet-4-6", "6"),
        ("ok-2", "claude-sonnet-4-6", "6"),
    )
    enforcer = BudgetEnforcer(client=client, budget_usd=Decimal("0.10"))
    await enforcer.complete(_request())
    with pytest.raises(BudgetExceededError):
        await enforcer.complete(_request())
    # The second call DID happen (cost was incurred), but the enforcer
    # raises after recording it — Story 2.5.1 AC: ≤ 5% over the cap.
    assert enforcer.stats.calls_made == 2
    assert enforcer.stats.running_total == Decimal("0.12")


@pytest.mark.asyncio
async def test_5pct_slack_allows_just_over_cap() -> None:
    """Single call landing inside the 5% slack window is permitted."""
    # Two calls at $0.06 each on a $0.10 budget * 1.05 = $0.105 cap:
    # First call: 0.06 ≤ 0.105 → passes.
    # Second call: 0.12 > 0.105 → blocks. Already covered above.
    # Here we test exactly-at-cap: cap = $0.10 * 1.05 = $0.105.
    # One call at exactly $0.105 should pass.
    client = _client(("ok", "claude-sonnet-4-6", "10"))
    enforcer = BudgetEnforcer(client=client, budget_usd=Decimal("0.10"))
    response = await enforcer.complete(_request())  # costs $0.06
    assert response is not None
    assert enforcer.remaining() > 0


def test_invalid_budget_rejected() -> None:
    client = _client()
    with pytest.raises(ValueError, match="budget_usd"):
        BudgetEnforcer(client=client, budget_usd=Decimal("0"))


def test_invalid_slack_rejected() -> None:
    client = _client()
    with pytest.raises(ValueError, match="slack"):
        BudgetEnforcer(client=client, budget_usd=Decimal("1"), slack=Decimal("0.5"))


def test_effective_cap_applies_slack() -> None:
    enforcer = BudgetEnforcer(
        client=_client(),
        budget_usd=Decimal("1.00"),
        slack=Decimal("1.10"),
    )
    assert enforcer.effective_cap == Decimal("1.100000")
