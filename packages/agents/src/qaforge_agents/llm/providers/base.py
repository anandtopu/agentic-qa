"""Provider Protocol and shared error types.

Adapters wrap vendor SDKs into a single ``complete`` coroutine that
returns text plus token counts. Cost computation, retries, redaction,
and structured-output validation live in the LLMClient — adapters are
deliberately thin.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from qaforge_agents.llm.types import Message


class ProviderError(Exception):
    """Raised by adapters on a non-recoverable provider failure."""

    def __init__(self, provider: str, message: str, *, transient: bool = False) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.transient = transient


class ProviderResponse(BaseModel):
    """The provider-side outcome of a single completion call."""

    content: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cached_prompt_tokens: int = Field(default=0, ge=0)
    raw: dict[str, object] = Field(default_factory=dict)


class Provider(Protocol):
    name: str

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        """Run one completion against the given model.

        Implementations should raise :class:`ProviderError` (with
        ``transient=True`` for retryable errors) and let the LLMClient
        handle backoff/failover.
        """
        ...
