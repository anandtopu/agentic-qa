"""Step Protocol + StepContext + StepResult."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from qaforge_agents.runtime.state import RunState


@dataclass(slots=True)
class StepContext:
    """Per-step state passed to every step function.

    ``shared`` is the workflow's running data — earlier steps put values
    here, later ones read them. The runtime makes a defensive copy in
    persistence so a step mutating ``shared`` doesn't mutate prior
    snapshots in the store.
    """

    workflow_id: UUID
    workspace_id: UUID
    correlation_id: str | None = None
    attempt: int = 1
    shared: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepResult:
    """What a step returns to the runtime."""

    output: dict[str, Any] = field(default_factory=dict)
    next_state: RunState | None = None  # if set, runtime transitions to this state
    pause: bool = False  # if True, runtime persists state and stops (e.g. approval)


StepFn = Callable[[StepContext], Awaitable[StepResult]]


class Step(Protocol):
    name: str
    target_state: RunState | None
    max_attempts: int

    async def run(self, ctx: StepContext) -> StepResult: ...


@dataclass(slots=True)
class FunctionStep:
    """Convenience adapter — wraps a plain async function as a :class:`Step`."""

    name: str
    fn: StepFn
    target_state: RunState | None = None
    max_attempts: int = 1

    async def run(self, ctx: StepContext) -> StepResult:
        return await self.fn(ctx)
