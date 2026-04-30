"""ToolRouter implementation."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ToolCallable = Callable[..., Awaitable[Any]]


class ToolNotFoundError(KeyError):
    pass


class ToolBudgetExceeded(RuntimeError):  # noqa: N818 - public name predates rule
    def __init__(self, tool_name: str, budget_seconds: int) -> None:
        super().__init__(f"tool {tool_name!r} exceeded wallclock budget of {budget_seconds}s")
        self.tool_name = tool_name
        self.budget_seconds = budget_seconds


@dataclass(slots=True)
class ToolDescriptor:
    """Resource budget declaration for one tool.

    The runner is the awaitable that actually does the work — typically
    a method bound on a stub/subprocess runner from one of the
    ``qaforge_tools.*`` packages.
    """

    name: str
    runner: ToolCallable
    max_wallclock_seconds: int = 600
    max_cpu_seconds: int | None = None  # informational — enforced by subprocess
    max_memory_mb: int | None = None  # informational — enforced by subprocess
    requires_approval: bool = False
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class _Invocation:
    name: str
    started_at: float
    finished_at: float
    duration_ms: int
    succeeded: bool
    error: str | None = None


class ToolRouter:
    """Dispatches calls to registered tools under a wallclock budget."""

    def __init__(self, descriptors: list[ToolDescriptor] | None = None) -> None:
        self._tools: dict[str, ToolDescriptor] = {}
        self._invocations: list[_Invocation] = []
        for descriptor in descriptors or []:
            self.register(descriptor)

    def register(self, descriptor: ToolDescriptor) -> None:
        if descriptor.name in self._tools:
            raise ValueError(f"tool {descriptor.name!r} is already registered")
        self._tools[descriptor.name] = descriptor

    def is_registered(self, name: str) -> bool:
        return name in self._tools

    def describe(self, name: str) -> ToolDescriptor:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def list_tools(self) -> list[ToolDescriptor]:
        return list(self._tools.values())

    @property
    def invocations(self) -> list[_Invocation]:
        return list(self._invocations)

    async def invoke(
        self,
        name: str,
        /,
        *args: Any,
        timeout_override: int | None = None,
        **kwargs: Any,
    ) -> Any:
        descriptor = self.describe(name)
        budget = (
            timeout_override if timeout_override is not None else descriptor.max_wallclock_seconds
        )

        started = time.monotonic()
        try:
            result = await asyncio.wait_for(descriptor.runner(*args, **kwargs), timeout=budget)
        except TimeoutError as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._invocations.append(
                _Invocation(
                    name=name,
                    started_at=started,
                    finished_at=time.monotonic(),
                    duration_ms=elapsed_ms,
                    succeeded=False,
                    error="timeout",
                )
            )
            raise ToolBudgetExceeded(name, budget) from exc
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._invocations.append(
                _Invocation(
                    name=name,
                    started_at=started,
                    finished_at=time.monotonic(),
                    duration_ms=elapsed_ms,
                    succeeded=False,
                    error=str(exc),
                )
            )
            raise

        elapsed_ms = int((time.monotonic() - started) * 1000)
        self._invocations.append(
            _Invocation(
                name=name,
                started_at=started,
                finished_at=time.monotonic(),
                duration_ms=elapsed_ms,
                succeeded=True,
            )
        )
        return result
