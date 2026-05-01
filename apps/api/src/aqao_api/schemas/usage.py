"""Usage / cost API schemas — Story 2.5.2."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UsageBucketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    usd_cost: Decimal
    prompt_tokens: int
    completion_tokens: int
    call_count: int


class UsageSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_usd_cost: Decimal
    total_prompt_tokens: int
    total_completion_tokens: int
    total_calls: int
    by_agent: list[UsageBucketResponse]
    by_provider: list[UsageBucketResponse]
    since: datetime | None
    until: datetime | None
