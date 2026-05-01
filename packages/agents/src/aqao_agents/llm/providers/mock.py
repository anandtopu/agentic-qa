"""In-memory provider for tests.

Lets tests script the response content, token counts, and failure mode
without touching the network or any vendor SDK.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from aqao_agents.llm.providers.base import Provider, ProviderError, ProviderResponse
from aqao_agents.llm.types import Message


@dataclass(slots=True)
class MockTurn:
    """One scripted response.

    Use ``error`` to simulate a transient or non-transient failure on
    this turn; the next turn proceeds as scripted.
    """

    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    error: ProviderError | None = None


class MockProvider:
    name = "mock"

    def __init__(self, turns: Iterable[MockTurn] | None = None) -> None:
        self._turns: deque[MockTurn] = deque(turns or [])
        self.calls: list[dict[str, object]] = []

    def queue(self, turn: MockTurn) -> None:
        self._turns.append(turn)

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
            }
        )

        if not self._turns:
            raise ProviderError(self.name, "no scripted turns left")

        turn = self._turns.popleft()
        if turn.error is not None:
            raise turn.error

        prompt_tokens = turn.prompt_tokens or sum(len(m.content) // 4 for m in messages)
        completion_tokens = turn.completion_tokens or max(1, len(turn.content) // 4)

        return ProviderResponse(
            content=turn.content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=turn.cached_prompt_tokens,
        )


# Marker for the Provider Protocol — explicit so mypy verifies conformance.
_: type[Provider] = MockProvider
