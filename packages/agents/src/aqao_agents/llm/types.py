"""Wire types for the LLM runtime.

Stable across providers; provider-specific extensions live in adapters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Tier(StrEnum):
    """Quality/cost tier. Maps to a list of (provider, model) candidates.

    See ADR-0004 for the default mapping.
    """

    HIGH = "high"
    MID = "mid"
    LOW = "low"


class Message(BaseModel):
    role: Role
    content: str


class ModelSpec(BaseModel):
    """A concrete provider+model pairing within a tier.

    ``model`` is the provider's wire identifier (e.g. ``claude-opus-4-7``).
    """

    provider: str
    model: str


class LLMRequest(BaseModel):
    """A single LLM call request.

    Provider, model, and pricing are resolved by the client from ``tier``;
    callers don't pick a model directly so cost tracking and failover stay
    centralised.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[Message]
    tier: Tier = Tier.MID
    response_schema: type[BaseModel] | None = None
    max_output_tokens: int = 4096
    temperature: float = 0.0
    workspace_id: UUID | None = None
    correlation_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class UsageRecord(BaseModel):
    """One row of cost/latency telemetry. Persisted to ``usage_records`` (PRD §12)."""

    provider: str
    model: str
    tier: Tier
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    usd_cost: Decimal
    latency_ms: int = Field(ge=0)
    correlation_id: str | None = None
    workspace_id: UUID | None = None
    started_at: datetime
    finished_at: datetime
    cached_prompt_tokens: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def now_utc(cls) -> datetime:
        return datetime.now(UTC)


class LLMResponse(BaseModel):
    """A successful response, plus the usage record that funded it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str
    structured: Any | None = None
    usage: UsageRecord
