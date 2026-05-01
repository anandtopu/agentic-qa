"""LLM runtime: provider-neutral client with cost accounting and redaction.

ADR-0004 mandates a single internal `LLMClient` that wraps every provider
SDK so cost tracking, redaction, retries, and provider failover are
centrally enforced. Agents never call SDKs directly.
"""

from aqao_agents.llm.client import LLMClient
from aqao_agents.llm.providers.base import Provider, ProviderResponse
from aqao_agents.llm.providers.mock import MockProvider
from aqao_agents.llm.recorder import (
    InMemoryRecorder,
    StructLogRecorder,
    UsageRecorder,
)
from aqao_agents.llm.types import (
    LLMRequest,
    LLMResponse,
    Message,
    ModelSpec,
    Role,
    Tier,
    UsageRecord,
)

__all__ = [
    "InMemoryRecorder",
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "MockProvider",
    "ModelSpec",
    "Provider",
    "ProviderResponse",
    "Role",
    "StructLogRecorder",
    "Tier",
    "UsageRecord",
    "UsageRecorder",
]
