"""Workflow persistence layer.

The runtime treats the store as opaque — anything that can write a
``StoredWorkflow`` row, append ``StoredStep`` rows, and read them back
satisfies the contract. The Control Plane backs this with the
``test_runs`` + ``agent_tasks`` tables (Story 1.6.1 migration); tests
use :class:`InMemoryWorkflowStore`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from qaforge_agents.runtime.state import RunState


@dataclass(slots=True)
class StoredStep:
    workflow_id: UUID
    step_index: int
    name: str
    state: str  # "pending" | "running" | "succeeded" | "failed" | "paused" | "skipped"
    input_json: dict[str, Any] = field(default_factory=dict)
    output_json: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0
    attempt: int = 1


@dataclass(slots=True)
class StoredWorkflow:
    id: UUID
    workspace_id: UUID
    state: RunState
    correlation_id: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowStore(Protocol):
    def upsert_workflow(self, workflow: StoredWorkflow) -> None: ...

    def get_workflow(self, workflow_id: UUID) -> StoredWorkflow | None: ...

    def upsert_step(self, step: StoredStep) -> None: ...

    def list_steps(self, workflow_id: UUID) -> list[StoredStep]: ...


class InMemoryWorkflowStore:
    """Reference implementation used in unit tests."""

    def __init__(self) -> None:
        self._workflows: dict[UUID, StoredWorkflow] = {}
        self._steps: dict[tuple[UUID, int], StoredStep] = {}

    def upsert_workflow(self, workflow: StoredWorkflow) -> None:
        self._workflows[workflow.id] = StoredWorkflow(
            id=workflow.id,
            workspace_id=workflow.workspace_id,
            state=workflow.state,
            correlation_id=workflow.correlation_id,
            summary=dict(workflow.summary),
            error=workflow.error,
            started_at=workflow.started_at,
            finished_at=workflow.finished_at,
        )

    def get_workflow(self, workflow_id: UUID) -> StoredWorkflow | None:
        return self._workflows.get(workflow_id)

    def upsert_step(self, step: StoredStep) -> None:
        self._steps[(step.workflow_id, step.step_index)] = StoredStep(
            workflow_id=step.workflow_id,
            step_index=step.step_index,
            name=step.name,
            state=step.state,
            input_json=dict(step.input_json),
            output_json=dict(step.output_json),
            error=step.error,
            started_at=step.started_at,
            finished_at=step.finished_at,
            duration_ms=step.duration_ms,
            attempt=step.attempt,
        )

    def list_steps(self, workflow_id: UUID) -> list[StoredStep]:
        steps = [s for (wf, _), s in self._steps.items() if wf == workflow_id]
        steps.sort(key=lambda s: s.step_index)
        return steps

    # --- test helpers ---------------------------------------------------------

    def all_workflows(self) -> Iterable[StoredWorkflow]:
        return list(self._workflows.values())


def utcnow() -> datetime:
    return datetime.now(UTC)
