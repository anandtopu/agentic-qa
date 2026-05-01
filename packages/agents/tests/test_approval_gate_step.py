"""Unit tests for ApprovalGateStep — Story 2.1.2.

Verifies the pause-and-resume contract: first execution requests an
approval and pauses, subsequent runs check the gate state and either
pause again, complete normally, or fail.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from aqao_agents.runtime import (
    ApprovalDecision,
    ApprovalDenied,
    ApprovalGateStep,
    InMemoryWorkflowStore,
    RunState,
    StepContext,
    WorkflowGraph,
    WorkflowRunner,
)


class _FakeGate:
    """In-memory ApprovalGate that records calls for assertions."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._decisions: dict[UUID, ApprovalDecision] = {}

    def request(
        self,
        *,
        workflow_id: UUID,
        workspace_id: UUID,
        event_type: str,
        subject: str,
        reason: str | None,
        gate_context: Mapping[str, Any],
    ) -> UUID:
        request_id = uuid.uuid4()
        self.requests.append(
            {
                "request_id": request_id,
                "workflow_id": workflow_id,
                "workspace_id": workspace_id,
                "event_type": event_type,
                "subject": subject,
                "reason": reason,
                "gate_context": dict(gate_context),
            }
        )
        # Default to pending until the test sets a decision.
        self._decisions[request_id] = ApprovalDecision(
            request_id=request_id,
            state="pending",
            decided_by=None,
            decided_at=None,
            comment=None,
        )
        return request_id

    def lookup(self, request_id: UUID) -> ApprovalDecision:
        return self._decisions[request_id]

    def set_decision(
        self,
        request_id: UUID,
        *,
        state: str,
        decided_by: UUID | None = None,
        comment: str | None = None,
    ) -> None:
        self._decisions[request_id] = ApprovalDecision(
            request_id=request_id,
            state=state,
            decided_by=decided_by,
            decided_at=datetime.now(UTC),
            comment=comment,
        )


def _ctx(shared: dict[str, Any] | None = None) -> StepContext:
    return StepContext(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        correlation_id="trace-1",
        shared=shared or {},
    )


@pytest.mark.asyncio
async def test_first_run_requests_approval_and_pauses() -> None:
    gate = _FakeGate()
    step = ApprovalGateStep(
        name="approve_drop",
        event_type="destructive_sql",
        subject="DROP TABLE legacy",
        gate=gate,
        reason="cleanup migration",
    )
    ctx = _ctx()

    result = await step.run(ctx)

    assert result.pause is True
    assert "approval_request_id" in result.output
    assert len(gate.requests) == 1
    req = gate.requests[0]
    assert req["event_type"] == "destructive_sql"
    assert req["subject"] == "DROP TABLE legacy"
    assert req["reason"] == "cleanup migration"
    assert req["gate_context"]["workflow_id"] == str(ctx.workflow_id)
    assert req["gate_context"]["correlation_id"] == "trace-1"


@pytest.mark.asyncio
async def test_resume_with_pending_state_pauses_again() -> None:
    gate = _FakeGate()
    step = ApprovalGateStep(
        name="approve_drop",
        event_type="destructive_sql",
        subject="DROP TABLE legacy",
        gate=gate,
    )
    request_id = gate.request(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        event_type="destructive_sql",
        subject="x",
        reason=None,
        gate_context={},
    )
    ctx = _ctx({"approval_request_id": str(request_id)})

    result = await step.run(ctx)

    assert result.pause is True
    assert result.output == {}
    # No second request was made — we reuse the pending one.
    assert len(gate.requests) == 1


@pytest.mark.asyncio
async def test_resume_with_approved_state_completes() -> None:
    gate = _FakeGate()
    request_id = gate.request(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        event_type="release_readiness",
        subject="release v1",
        reason=None,
        gate_context={},
    )
    user_id = uuid.uuid4()
    gate.set_decision(request_id, state="approved", decided_by=user_id, comment="LGTM")

    step = ApprovalGateStep(
        name="release",
        event_type="release_readiness",
        subject="release v1",
        gate=gate,
    )
    ctx = _ctx({"approval_request_id": str(request_id)})

    result = await step.run(ctx)

    assert result.pause is False
    assert result.output["approval_state"] == "approved"
    assert result.output["approval_decided_by"] == str(user_id)
    assert result.output["approval_comment"] == "LGTM"


@pytest.mark.parametrize(
    "decision_state",
    ["rejected", "expired", "cancelled"],
)
@pytest.mark.asyncio
async def test_resume_with_denial_raises(decision_state: str) -> None:
    gate = _FakeGate()
    request_id = gate.request(
        workflow_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        event_type="destructive_sql",
        subject="DROP",
        reason=None,
        gate_context={},
    )
    gate.set_decision(request_id, state=decision_state, comment="nope")

    step = ApprovalGateStep(
        name="approve",
        event_type="destructive_sql",
        subject="DROP",
        gate=gate,
    )
    ctx = _ctx({"approval_request_id": str(request_id)})

    with pytest.raises(ApprovalDenied) as exc:
        await step.run(ctx)
    assert exc.value.state == decision_state
    assert exc.value.comment == "nope"


@pytest.mark.asyncio
async def test_runner_stops_workflow_on_pause_and_resumes_after_approval() -> None:
    """End-to-end: a graph with an approval step pauses, then resumes
    cleanly when the gate flips to approved on a second run."""
    gate = _FakeGate()
    step = ApprovalGateStep(
        name="gate",
        event_type="destructive_sql",
        subject="DROP",
        gate=gate,
    )
    graph = WorkflowGraph.of("demo", [step])

    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)

    workflow_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    first = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=workspace_id)
    assert first.paused is True
    assert first.final_state is RunState.PAUSED_FOR_APPROVAL
    assert len(gate.requests) == 1

    request_id = gate.requests[0]["request_id"]
    gate.set_decision(request_id, state="approved")

    second = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=workspace_id)
    assert second.paused is False
    assert second.final_state is RunState.DONE


@pytest.mark.asyncio
async def test_runner_records_failed_workflow_on_denial() -> None:
    gate = _FakeGate()
    step = ApprovalGateStep(
        name="gate",
        event_type="release_readiness",
        subject="release v1",
        gate=gate,
    )
    graph = WorkflowGraph.of("demo", [step])

    store = InMemoryWorkflowStore()
    runner = WorkflowRunner(store)

    workflow_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    first = await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=workspace_id)
    assert first.paused is True

    request_id = gate.requests[0]["request_id"]
    gate.set_decision(request_id, state="rejected", comment="not safe")

    from aqao_agents.runtime import WorkflowExecutionError

    with pytest.raises(WorkflowExecutionError):
        await runner.run(graph=graph, workflow_id=workflow_id, workspace_id=workspace_id)

    persisted = store.get_workflow(workflow_id)
    assert persisted is not None
    assert persisted.state is RunState.FAILED
