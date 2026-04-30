"""Unit tests for the tool router — Story 1.6.2."""

from __future__ import annotations

import asyncio

import pytest

from qaforge_tools.router import (
    ToolBudgetExceeded,
    ToolDescriptor,
    ToolNotFoundError,
    ToolRouter,
)


def _router_with(*descriptors: ToolDescriptor) -> ToolRouter:
    return ToolRouter(list(descriptors))


@pytest.mark.asyncio
async def test_invoke_dispatches_to_registered_tool() -> None:
    async def runner(value: int) -> int:
        return value * 2

    router = _router_with(ToolDescriptor(name="doubler", runner=runner, max_wallclock_seconds=5))
    result = await router.invoke("doubler", 21)
    assert result == 42


@pytest.mark.asyncio
async def test_invoke_unknown_tool_raises_not_found() -> None:
    router = ToolRouter()
    with pytest.raises(ToolNotFoundError):
        await router.invoke("missing")


@pytest.mark.asyncio
async def test_wallclock_budget_enforced() -> None:
    async def runner() -> str:
        await asyncio.sleep(0.5)
        return "done"

    router = _router_with(ToolDescriptor(name="slow", runner=runner, max_wallclock_seconds=1))
    # 1s budget should accommodate the 0.5s call.
    assert await router.invoke("slow") == "done"


@pytest.mark.asyncio
async def test_wallclock_budget_overrun_raises() -> None:
    async def runner() -> str:
        await asyncio.sleep(0.3)
        return "done"

    router = _router_with(
        ToolDescriptor(name="overshoot", runner=runner, max_wallclock_seconds=600)
    )
    with pytest.raises(ToolBudgetExceeded) as exc_info:
        await router.invoke("overshoot", timeout_override=0)
    assert exc_info.value.tool_name == "overshoot"


@pytest.mark.asyncio
async def test_invocation_log_records_success_and_failure() -> None:
    async def ok() -> str:
        return "ok"

    async def bad() -> str:
        raise RuntimeError("kaboom")

    router = _router_with(
        ToolDescriptor(name="ok", runner=ok),
        ToolDescriptor(name="bad", runner=bad),
    )
    await router.invoke("ok")
    with pytest.raises(RuntimeError, match="kaboom"):
        await router.invoke("bad")

    invocations = router.invocations
    assert len(invocations) == 2
    assert invocations[0].succeeded
    assert not invocations[1].succeeded
    assert invocations[1].error == "kaboom"


def test_register_rejects_duplicate_name() -> None:
    async def r1() -> None:
        return None

    descriptor = ToolDescriptor(name="x", runner=r1)
    router = ToolRouter([descriptor])
    with pytest.raises(ValueError, match="already registered"):
        router.register(descriptor)


def test_describe_returns_descriptor() -> None:
    async def r() -> int:
        return 0

    descriptor = ToolDescriptor(
        name="z", runner=r, max_wallclock_seconds=42, requires_approval=True
    )
    router = ToolRouter([descriptor])
    assert router.describe("z").requires_approval is True


def test_list_tools_returns_all_registered() -> None:
    async def r() -> None:
        return None

    router = _router_with(
        ToolDescriptor(name="a", runner=r),
        ToolDescriptor(name="b", runner=r),
    )
    names = sorted(d.name for d in router.list_tools())
    assert names == ["a", "b"]
