"""Unit tests for the workflow runtime — Story 1.6.1."""

from __future__ import annotations

import uuid

import pytest

from qaforge_agents.runtime import (
    InMemoryWorkflowStore,
    RunState,
    StepContext,
    StepResult,
    WorkflowExecutionError,
    WorkflowGraph,
    WorkflowRunner,
)
from qaforge_agents.runtime.step import FunctionStep

WS = uuid.uuid4()


def _step(name: str, *, output: dict[str, object] | None = None, max_attempts: int = 1):
    async def _fn(ctx: StepContext) -> StepResult:
        return StepResult(output=output or {})

    return FunctionStep(name=name, fn=_fn, max_attempts=max_attempts)


def _failing_step(name: str, *, fail_attempts: int, max_attempts: int):
    state = {"calls": 0}

    async def _fn(ctx: StepContext) -> StepResult:
        state["calls"] += 1
        if state["calls"] <= fail_attempts:
            raise RuntimeError(f"transient failure attempt {ctx.attempt}")
        return StepResult(output={f"{name}_calls": state["calls"]})

    return FunctionStep(name=name, fn=_fn, max_attempts=max_attempts)


@pytest.mark.asyncio
async def test_runs_all_steps_in_order_and_marks_done() -> None:
    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)
    graph = WorkflowGraph.of(
        "demo",
        [
            _step("plan", output={"plan_ok": True}),
            _step("execute", output={"execute_ok": True}),
        ],
    )
    workflow_id = uuid.uuid4()
    result = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=WS)
    assert result.final_state is RunState.DONE
    assert result.steps_executed == 2

    persisted = store.get_workflow(workflow_id)
    assert persisted is not None
    assert persisted.state is RunState.DONE
    assert persisted.summary == {"plan_ok": True, "execute_ok": True}


@pytest.mark.asyncio
async def test_resume_skips_succeeded_steps() -> None:
    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)
    workflow_id = uuid.uuid4()

    invocations = {"calls": 0}

    async def first(ctx: StepContext) -> StepResult:
        invocations["calls"] += 1
        return StepResult(output={"first": True})

    async def second(ctx: StepContext) -> StepResult:
        invocations["calls"] += 1
        return StepResult(output={"second": True})

    graph_v1 = WorkflowGraph.of("resumable", [FunctionStep(name="first", fn=first)])
    await runner.run(graph=graph_v1, workflow_id=workflow_id, workspace_id=WS)

    # Re-run with a longer graph; the first step is already 'succeeded'.
    graph_v2 = WorkflowGraph.of(
        "resumable",
        [FunctionStep(name="first", fn=first), FunctionStep(name="second", fn=second)],
    )

    # Need to manually flip state back to executing since v1 already marked it DONE.
    workflow = store.get_workflow(workflow_id)
    assert workflow is not None
    workflow.state = RunState.EXECUTING
    store.upsert_workflow(workflow)

    result = await runner.run(graph=graph_v2, workflow_id=workflow_id, workspace_id=WS)
    # `first` should not have re-executed.
    assert invocations["calls"] == 2
    assert result.steps_executed == 1


@pytest.mark.asyncio
async def test_transient_failure_retries_within_budget() -> None:
    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)
    graph = WorkflowGraph.of(
        "retryable",
        [_failing_step("flaky", fail_attempts=2, max_attempts=3)],
    )
    workflow_id = uuid.uuid4()
    result = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=WS)
    assert result.final_state is RunState.DONE
    persisted_steps = store.list_steps(workflow_id)
    # Latest persisted attempt for the step should reflect the successful one.
    assert persisted_steps[-1].state == "succeeded"
    assert persisted_steps[-1].attempt == 3


@pytest.mark.asyncio
async def test_failure_after_exhausting_retries_marks_workflow_failed() -> None:
    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)
    graph = WorkflowGraph.of(
        "doomed",
        [_failing_step("always_fails", fail_attempts=10, max_attempts=2)],
    )
    workflow_id = uuid.uuid4()

    with pytest.raises(WorkflowExecutionError) as exc_info:
        await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=WS)
    assert exc_info.value.attempts == 2

    workflow = store.get_workflow(workflow_id)
    assert workflow is not None
    assert workflow.state is RunState.FAILED
    assert workflow.error is not None


@pytest.mark.asyncio
async def test_pause_returns_and_persists_paused_state() -> None:
    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)

    async def gate(ctx: StepContext) -> StepResult:
        return StepResult(output={"awaiting": True}, pause=True)

    async def post(ctx: StepContext) -> StepResult:
        return StepResult(output={"resumed": True})

    graph = WorkflowGraph.of(
        "approval",
        [
            FunctionStep(name="gate", fn=gate),
            FunctionStep(name="post", fn=post),
        ],
    )
    workflow_id = uuid.uuid4()
    result = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=WS)
    assert result.paused
    assert result.final_state is RunState.PAUSED_FOR_APPROVAL
    persisted = store.get_workflow(workflow_id)
    assert persisted is not None
    assert persisted.state is RunState.PAUSED_FOR_APPROVAL


@pytest.mark.asyncio
async def test_terminal_workflow_is_no_op_on_re_run() -> None:
    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)
    graph = WorkflowGraph.of("done", [_step("only", output={"x": 1})])
    workflow_id = uuid.uuid4()

    first = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=WS)
    assert first.final_state is RunState.DONE

    second = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=WS)
    assert second.steps_executed == 0
    assert second.final_state is RunState.DONE


def test_graph_rejects_duplicate_step_names() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        WorkflowGraph.of("dup", [_step("a"), _step("a")])
