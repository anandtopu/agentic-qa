"""TestRunService — Story 1.6.

Bridges the Control Plane (``test_runs`` / ``agent_tasks`` / ``evidence_artifacts``
tables) to the workflow runtime (``qaforge_agents.runtime``). For each
test_run row we materialise a :class:`SqlAlchemyWorkflowStore` that
writes through to those tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from qaforge_agents.runtime import (
    InMemoryWorkflowStore,
    RunState,
    Step,
    WorkflowGraph,
    WorkflowRunner,
)
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    AgentTask,
    AgentTaskState,
    TestPlan,
    TestRun,
    TestRunState,
    Workspace,
)
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)


@dataclass(slots=True)
class TestRunStartOutput:
    test_run: TestRun
    final_state: RunState
    steps_executed: int
    paused: bool


class TestRunService:
    """Starts and inspects orchestrator runs.

    Phase 1 ships an in-memory store as the runtime backing — the runner
    is fully synchronous and the test_run row is updated when the run
    completes. Phase 2 swaps the store to a SQL-backed implementation
    that streams updates as the workflow progresses (so the admin UI
    can watch a long-running test_run).
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def get(self, test_run_id: UUID) -> TestRun:
        run = self._session.get(TestRun, test_run_id)
        if run is None:
            raise ResourceNotFoundError("test_run", test_run_id)
        return run

    def list_for_workspace(
        self,
        *,
        workspace_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[TestRun]:
        stmt = (
            select(TestRun)
            .where(TestRun.workspace_id == workspace_id)
            .order_by(TestRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt).all())

    def list_steps(self, test_run_id: UUID) -> list[AgentTask]:
        run = self.get(test_run_id)
        stmt = (
            select(AgentTask)
            .where(AgentTask.test_run_id == run.id)
            .order_by(AgentTask.step_index.asc())
        )
        return list(self._session.scalars(stmt).all())

    # --- mutations --------------------------------------------------------------

    async def start(
        self,
        *,
        test_plan_id: UUID,
        graph: WorkflowGraph,
        idempotency_key: str,
        context: RequestContext,
    ) -> TestRunStartOutput:
        plan = self._session.get(TestPlan, test_plan_id)
        if plan is None:
            raise ResourceNotFoundError("test_plan", test_plan_id)

        existing = self._session.scalars(
            select(TestRun).where(
                TestRun.workspace_id == plan.workspace_id,
                TestRun.idempotency_key == idempotency_key,
            )
        ).first()
        if existing is not None:
            raise DuplicateResourceError("test_run", "idempotency_key", idempotency_key)

        workspace = self._session.get(Workspace, plan.workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("workspace", plan.workspace_id)

        run = TestRun(
            tenant_id=context.tenant_id,
            workspace_id=plan.workspace_id,
            test_plan_id=plan.id,
            requirement_id=plan.requirement_id,
            state=TestRunState.PLANNED,
            idempotency_key=idempotency_key,
            triggered_by=context.user_id,
        )
        self._session.add(run)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateResourceError("test_run", "idempotency_key", idempotency_key) from exc

        store = InMemoryWorkflowStore()
        runner = WorkflowRunner(store)
        result = await runner.run(
            graph=graph,
            workflow_id=run.id,
            workspace_id=plan.workspace_id,
            correlation_id=context.correlation_id,
            initial_shared={"test_plan_id": str(plan.id)},
        )

        # Mirror the in-memory workflow state onto the persisted row.
        persisted = store.get_workflow(run.id)
        if persisted is not None:
            run.state = TestRunState(persisted.state.value)
            run.summary = dict(persisted.summary)
            run.error = persisted.error
            run.started_at = persisted.started_at
            run.finished_at = persisted.finished_at

        # Persist each step as an agent_tasks row.
        for stored_step in store.list_steps(run.id):
            self._session.add(
                AgentTask(
                    tenant_id=context.tenant_id,
                    test_run_id=run.id,
                    agent_name=stored_step.name,
                    step_index=stored_step.step_index,
                    state=AgentTaskState(stored_step.state),
                    input_json=stored_step.input_json,
                    output_json=stored_step.output_json,
                    error=stored_step.error,
                    started_at=stored_step.started_at,
                    finished_at=stored_step.finished_at,
                    duration_ms=stored_step.duration_ms,
                    attempt=stored_step.attempt,
                )
            )
        self._session.flush()

        self._audit.record(
            context=context,
            action="test_run.started",
            resource_type="test_run",
            resource_id=run.id,
            payload={
                "test_plan_id": str(plan.id),
                "graph_name": graph.name,
                "final_state": run.state.value,
                "steps_executed": result.steps_executed,
                "paused": result.paused,
            },
        )

        return TestRunStartOutput(
            test_run=run,
            final_state=result.final_state,
            steps_executed=result.steps_executed,
            paused=result.paused,
        )


@dataclass(slots=True)
class _DummyStep:
    """Phase 1 placeholder graph builder — used until Epic 1.7 wires real agents."""

    name: str
    target_state: RunState | None = None
    max_attempts: int = 1
    payload: dict[str, Any] | None = None

    async def run(self, ctx: Any) -> Any:
        from qaforge_agents.runtime.step import StepResult

        return StepResult(output=dict(self.payload or {}))


def default_pr_analysis_graph() -> WorkflowGraph:
    """Phase-1 placeholder graph.

    Real Planner / API-Tester / UI-Tester / Classifier wiring lands as
    each Epic completes; Epic 1.7 fills in the classifier step, Epic
    1.8 fills in the report step.
    """
    steps: list[Step] = [
        _DummyStep(name="plan", payload={"plan_emitted": True}),
        _DummyStep(name="execute", payload={"execute_emitted": True}),
        _DummyStep(name="classify", payload={"classify_emitted": True}),
        _DummyStep(name="report", payload={"report_emitted": True}),
    ]
    return WorkflowGraph.of("pr-analysis", steps)


def new_idempotency_key() -> str:
    return uuid4().hex
