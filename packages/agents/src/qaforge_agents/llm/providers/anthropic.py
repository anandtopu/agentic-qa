"""Anthropic provider adapter.

The first production provider. Phase 0 ships the wiring; ADR-0004 lists
Anthropic as the default and Story 0.4.2 requires that every call goes
through this adapter (never the SDK directly) so cost tracking and
redaction stay centralised.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from qaforge_agents.llm.providers.base import Provider, ProviderError, ProviderResponse
from qaforge_agents.llm.types import Message, Role

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from anthropic import AsyncAnthropic


_TRANSIENT_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    @classmethod
    def from_env(cls, api_key: str | None = None) -> AnthropicProvider:
        from anthropic import AsyncAnthropic

        return cls(AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic())

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        system_text, conversation = _split_system(messages)

        try:
            result = await self._client.messages.create(
                model=model,
                max_tokens=max_output_tokens,
                temperature=temperature,
                system=system_text,
                messages=[
                    {
                        "role": cast("Literal['user', 'assistant']", m.role.value),
                        "content": m.content,
                    }
                    for m in conversation
                ],
            )
        except Exception as exc:
            transient = _is_transient(exc)
            raise ProviderError(self.name, str(exc), transient=transient) from exc

        content = _join_text_blocks(result.content)
        usage = result.usage
        return ProviderResponse(
            content=content,
            prompt_tokens=int(usage.input_tokens),
            completion_tokens=int(usage.output_tokens),
            cached_prompt_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            raw={"model": result.model, "stop_reason": result.stop_reason},
        )


def _split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    system_chunks = [m.content for m in messages if m.role is Role.SYSTEM]
    rest = [m for m in messages if m.role is not Role.SYSTEM]
    return ("\n\n".join(system_chunks), rest)


def _join_text_blocks(blocks: object) -> str:
    """Anthropic returns a list of blocks; concatenate text-typed ones."""
    parts: list[str] = []
    for block in cast("list[object]", blocks):
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _is_transient(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in _TRANSIENT_STATUS_CODES:
        return True
    return type(exc).__name__ in {"APITimeoutError", "APIConnectionError", "RateLimitError"}


# Marker for the Provider Protocol — explicit so mypy verifies conformance.
_: type[Provider] = AnthropicProvider
