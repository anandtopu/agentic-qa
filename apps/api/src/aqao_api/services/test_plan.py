"""TestPlanService — Story 1.3.1.

Glues the Planner agent (``aqao_agents.planner``) to persistence and
audit. The agent itself never sees the DB.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_agents.planner import (
    PlannerAgent,
    PlannerInput,
    PlannerTestPlan,
)
from aqao_api.auth.context import RequestContext
from aqao_api.db.models import (
    Requirement,
    TestCase,
    TestPlan,
    TestPlanStatus,
    Workspace,
)
from aqao_api.db.models.test_plan import TestCasePriority, TestCaseType
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import ResourceNotFoundError


class TestPlanService:
    def __init__(self, session: Session, planner: PlannerAgent) -> None:
        self._session = session
        self._planner = planner
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def get(self, test_plan_id: UUID) -> TestPlan:
        plan = self._session.get(TestPlan, test_plan_id)
        if plan is None:
            raise ResourceNotFoundError("test_plan", test_plan_id)
        return plan

    def list_for_workspace(
        self,
        *,
        workspace_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[TestPlan]:
        stmt = (
            select(TestPlan)
            .where(TestPlan.workspace_id == workspace_id)
            .order_by(TestPlan.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt).all())

    # --- mutations --------------------------------------------------------------

    async def generate(
        self,
        *,
        requirement_id: UUID,
        context: RequestContext,
        existing_test_titles: list[str] | None = None,
    ) -> TestPlan:
        requirement = self._session.get(Requirement, requirement_id)
        if requirement is None:
            raise ResourceNotFoundError("requirement", requirement_id)

        workspace = self._session.get(Workspace, requirement.workspace_id)
        workspace_context = (
            {
                "name": workspace.name,
                "application_type": (
                    workspace.application_type.value if workspace is not None else None
                ),
                "environments": list(workspace.environments) if workspace else [],
            }
            if workspace is not None
            else None
        )

        output = await self._planner.plan(
            PlannerInput(
                requirement_id=requirement.id,
                requirement_type=requirement.type.value,
                requirement_summary=str(
                    requirement.parsed.get("summary") or requirement.source_ref or ""
                ),
                parsed_payload=dict(requirement.parsed),
                workspace_context=workspace_context,
                existing_test_titles=existing_test_titles or [],
                correlation_id=context.correlation_id,
                workspace_id=requirement.workspace_id,
            )
        )

        plan_row = self._persist(
            workspace_id=requirement.workspace_id,
            requirement_id=requirement.id,
            plan=output.plan,
            context=context,
            model_id=output.usage.model,
            prompt_version=output.prompt_version,
            usd_cost_cents=round(float(output.usage.usd_cost) * 100),
            latency_ms=output.usage.latency_ms,
        )

        self._audit.record(
            context=context,
            action="test_plan.generated",
            resource_type="test_plan",
            resource_id=plan_row.id,
            payload={
                "requirement_id": str(requirement.id),
                "model": output.usage.model,
                "prompt_version": output.prompt_version,
                "test_case_count": len(output.plan.test_cases),
                "open_question_count": len(output.plan.open_questions),
                "usd_cost": str(output.usage.usd_cost),
            },
        )
        return plan_row

    # --- helpers ----------------------------------------------------------------

    def _persist(
        self,
        *,
        workspace_id: UUID,
        requirement_id: UUID,
        plan: PlannerTestPlan,
        context: RequestContext,
        model_id: str,
        prompt_version: str,
        usd_cost_cents: int,
        latency_ms: int,
    ) -> TestPlan:
        plan_row = TestPlan(
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            requirement_id=requirement_id,
            summary=plan.summary,
            status=TestPlanStatus.DRAFT,
            coverage_areas=list(plan.coverage_areas),
            open_questions=list(plan.open_questions),
            plan_payload=plan.model_dump(mode="json"),
            generated_by_model=model_id,
            generated_by_prompt_version=prompt_version,
            usd_cost=usd_cost_cents,
            latency_ms=latency_ms,
        )
        self._session.add(plan_row)
        self._session.flush()

        for case in plan.test_cases:
            self._session.add(
                TestCase(
                    tenant_id=context.tenant_id,
                    test_plan_id=plan_row.id,
                    title=case.title,
                    type=TestCaseType(case.type.value),
                    priority=TestCasePriority(case.priority.value),
                    preconditions=list(case.preconditions),
                    steps=list(case.steps),
                    expected_result=case.expected_result,
                    automation_candidate=case.automation_candidate,
                    tags=list(case.tags),
                )
            )
        self._session.flush()
        return plan_row
