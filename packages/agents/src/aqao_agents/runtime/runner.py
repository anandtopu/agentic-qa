"""WorkflowRunner — drives a :class:`WorkflowGraph` to completion.

Story 1.6.1 acceptance:

* Idempotent retries — each step has ``max_attempts``; transient failures
  retry up to that bound, then mark the workflow ``failed``. The store
  reflects every attempt.
* Stuck workflows visible — every state transition (run → step → run)
  is persisted so an admin UI listing ``test_runs`` can spot a workflow
  that hasn't progressed.
* Pause-and-resume — a step can return ``pause=True`` (e.g. waiting on
  human approval) and the runtime stops cleanly. The same workflow id
  can be resumed from the next pending step.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from aqao_agents.runtime.graph import WorkflowGraph
from aqao_agents.runtime.persistence import (
    StoredStep,
    StoredWorkflow,
    WorkflowStore,
    utcnow,
)
from aqao_agents.runtime.state import RunState
from aqao_agents.runtime.step import StepContext, StepResult


class WorkflowExecutionError(RuntimeError):
    """A step failed and exhausted its retry budget."""

    def __init__(self, step_name: str, attempts: int, original: BaseException) -> None:
        super().__init__(f"step {step_name!r} failed after {attempts} attempt(s): {original}")
        self.step_name = step_name
        self.attempts = attempts
        self.original = original


class StepFailed(RuntimeError):  # noqa: N818 - public name predates rule
    """A step's run() raised. Wrapped to preserve traceback in the store."""


@dataclass(slots=True)
class WorkflowRunResult:
    workflow_id: UUID
    final_state: RunState
    steps_executed: int
    paused: bool = False
    error: str | None = None
    shared: dict[str, Any] = field(default_factory=dict)


class WorkflowRunner:
    """Synchronous step-by-step driver. Phase 2 wraps in Celery."""

    def __init__(self, store: WorkflowStore) -> None:
        self._store = store

    async def run(
        self,
        *,
        graph: WorkflowGraph,
        workflow_id: UUID,
        workspace_id: UUID,
        correlation_id: str | None = None,
        initial_shared: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        workflow = self._load_or_create(
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
        )
        if workflow.state.is_terminal:
            return WorkflowRunResult(
                workflow_id=workflow.id,
                final_state=workflow.state,
                steps_executed=0,
                error=workflow.error,
            )

        existing_steps = {s.step_index: s for s in self._store.list_steps(workflow.id)}
        shared: dict[str, Any] = dict(initial_shared or {})
        # Paused steps emitted output (e.g. an approval_request_id) that
        # later attempts need; succeeded steps obviously did too.
        for st in sorted(existing_steps.values(), key=lambda s: s.step_index):
            if st.state in {"succeeded", "paused"}:
                shared.update(st.output_json)

        workflow.state = RunState.EXECUTING
        if workflow.started_at is None:
            workflow.started_at = utcnow()
        self._store.upsert_workflow(workflow)

        steps_executed = 0
        paused = False

        for index, step in enumerate(graph):
            stored = existing_steps.get(index)
            if stored is not None and stored.state == "succeeded":
                continue  # idempotent resume

            attempt = 0
            success = False
            last_error: BaseException | None = None
            while attempt < step.max_attempts and not success:
                attempt += 1
                context = StepContext(
                    workflow_id=workflow.id,
                    workspace_id=workflow.workspace_id,
                    correlation_id=workflow.correlation_id,
                    attempt=attempt,
                    shared=dict(shared),
                )
                self._store.upsert_step(
                    StoredStep(
                        workflow_id=workflow.id,
                        step_index=index,
                        name=step.name,
                        state="running",
                        attempt=attempt,
                        started_at=utcnow(),
                    )
                )
                t0 = time.monotonic()
                try:
                    result: StepResult = await step.run(context)
                except Exception as exc:
                    last_error = exc
                    self._store.upsert_step(
                        StoredStep(
                            workflow_id=workflow.id,
                            step_index=index,
                            name=step.name,
                            state="failed",
                            attempt=attempt,
                            error=traceback.format_exc(),
                            duration_ms=int((time.monotonic() - t0) * 1000),
                            started_at=utcnow(),
                            finished_at=utcnow(),
                        )
                    )
                    continue

                duration_ms = int((time.monotonic() - t0) * 1000)
                shared.update(result.output)
                # Paused steps are recorded with state="paused" so the
                # next runner pass re-drives them and can react to a
                # decision that landed in the meantime.
                step_state = "paused" if result.pause else "succeeded"
                self._store.upsert_step(
                    StoredStep(
                        workflow_id=workflow.id,
                        step_index=index,
                        name=step.name,
                        state=step_state,
                        attempt=attempt,
                        output_json=dict(result.output),
                        duration_ms=duration_ms,
                        started_at=utcnow(),
                        finished_at=utcnow(),
                    )
                )
                steps_executed += 1
                success = True

                if result.next_state is not None:
                    workflow.state = result.next_state
                    self._store.upsert_workflow(workflow)

                if result.pause:
                    workflow.state = RunState.PAUSED_FOR_APPROVAL
                    self._store.upsert_workflow(workflow)
                    return WorkflowRunResult(
                        workflow_id=workflow.id,
                        final_state=workflow.state,
                        steps_executed=steps_executed,
                        paused=True,
                        shared=shared,
                    )

            if not success:
                assert last_error is not None
                workflow.state = RunState.FAILED
                workflow.error = str(last_error)
                workflow.finished_at = utcnow()
                self._store.upsert_workflow(workflow)
                raise WorkflowExecutionError(
                    step_name=step.name,
                    attempts=attempt,
                    original=last_error,
                )

        workflow.state = RunState.DONE
        workflow.finished_at = utcnow()
        workflow.summary = dict(shared)
        self._store.upsert_workflow(workflow)
        return WorkflowRunResult(
            workflow_id=workflow.id,
            final_state=workflow.state,
            steps_executed=steps_executed,
            paused=paused,
            shared=shared,
        )

    def _load_or_create(
        self,
        *,
        workflow_id: UUID,
        workspace_id: UUID,
        correlation_id: str | None,
    ) -> StoredWorkflow:
        existing = self._store.get_workflow(workflow_id)
        if existing is not None:
            return existing
        workflow = StoredWorkflow(
            id=workflow_id,
            workspace_id=workspace_id,
            state=RunState.PLANNED,
            correlation_id=correlation_id,
        )
        self._store.upsert_workflow(workflow)
        return workflow
