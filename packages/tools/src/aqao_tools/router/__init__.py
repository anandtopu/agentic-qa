"""Typed tool router — Story 1.6.2.

Every tool the platform runs (Newman, pytest, Playwright, …) is dispatched
through this registry. Each tool declares its resource budget; the router
enforces wallclock via :func:`asyncio.wait_for` and surfaces budget
overruns as :class:`ToolBudgetExceeded`.

CPU/RAM caps are documented per tool but enforced by the underlying
subprocess wrapper (or, in production, by the container/orchestrator) —
the router only owns wallclock.
"""

from aqao_tools.router.registry import (
    ToolBudgetExceeded,
    ToolCallable,
    ToolDescriptor,
    ToolNotFoundError,
    ToolRouter,
)

__all__ = [
    "ToolBudgetExceeded",
    "ToolCallable",
    "ToolDescriptor",
    "ToolNotFoundError",
    "ToolRouter",
]
