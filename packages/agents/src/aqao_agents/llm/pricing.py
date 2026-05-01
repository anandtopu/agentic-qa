"""USD-per-token pricing tables for the supported provider models.

Updated as providers publish new prices. The numbers below reflect the
list price per **1 million tokens**, separated into ``input`` and
``output`` rates. Cached prompt tokens are billed at 10% of input by
default (override per-model where the provider differs).

Story 0.4.2 acceptance: total recorded cost must match the provider
invoice within ±2% over a calibration week. That is a measurement
target — accuracy comes from keeping this table fresh.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    """Pricing in USD per 1M tokens."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Decimal | None = Field(
        default=None,
        description="Cached prompt token rate; defaults to 10% of input when unset.",
    )

    def cost_for(
        self, *, prompt_tokens: int, completion_tokens: int, cached_prompt_tokens: int = 0
    ) -> Decimal:
        if cached_prompt_tokens > prompt_tokens:
            raise ValueError("cached_prompt_tokens cannot exceed prompt_tokens")

        cached_rate = self.cached_input_per_mtok or (self.input_per_mtok / Decimal(10))
        billable_input = prompt_tokens - cached_prompt_tokens

        return (
            (Decimal(billable_input) * self.input_per_mtok / Decimal(1_000_000))
            + (Decimal(cached_prompt_tokens) * cached_rate / Decimal(1_000_000))
            + (Decimal(completion_tokens) * self.output_per_mtok / Decimal(1_000_000))
        )


PricingTable = dict[tuple[str, str], ModelPricing]


def default_pricing() -> PricingTable:
    """Built-in pricing as of 2026-04. Override per workspace if needed."""
    return {
        ("anthropic", "claude-opus-4-7"): ModelPricing(
            input_per_mtok=Decimal("15.00"), output_per_mtok=Decimal("75.00")
        ),
        ("anthropic", "claude-sonnet-4-6"): ModelPricing(
            input_per_mtok=Decimal("3.00"), output_per_mtok=Decimal("15.00")
        ),
        ("anthropic", "claude-haiku-4-5"): ModelPricing(
            input_per_mtok=Decimal("1.00"), output_per_mtok=Decimal("5.00")
        ),
        ("openai", "gpt-5.1"): ModelPricing(
            input_per_mtok=Decimal("5.00"), output_per_mtok=Decimal("20.00")
        ),
        ("openai", "gpt-5.1-mini"): ModelPricing(
            input_per_mtok=Decimal("1.00"), output_per_mtok=Decimal("4.00")
        ),
        ("google", "gemini-2.5-pro"): ModelPricing(
            input_per_mtok=Decimal("3.00"), output_per_mtok=Decimal("15.00")
        ),
        ("google", "gemini-2.5-flash"): ModelPricing(
            input_per_mtok=Decimal("0.30"), output_per_mtok=Decimal("1.50")
        ),
        ("mock", "mock-model"): ModelPricing(
            input_per_mtok=Decimal("0.00"), output_per_mtok=Decimal("0.00")
        ),
    }
