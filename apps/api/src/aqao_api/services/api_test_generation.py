"""ApiTestGenerationService — Story 1.4.

Glue between :class:`ApiTesterAgent` and the Control Plane: looks up the
test plan, finds the upstream OpenAPI requirement, calls the agent,
and persists the generated source on the matching test cases.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_agents.api_tester import (
    ApiTesterAgent,
    ApiTesterInput,
    GeneratedTestSuite,
)
from aqao_api.auth.context import RequestContext
from aqao_api.db.models import (
    Requirement,
    RequirementType,
    TestCase,
    TestPlan,
)
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import ResourceNotFoundError, ServiceError


class NoOpenApiRequirementError(ServiceError):
    """Raised when the test plan's requirement is not an OpenAPI ingest."""


@dataclass(slots=True)
class ApiTestGenerationOutput:
    test_plan_id: UUID
    suite: GeneratedTestSuite
    cases_updated: int
    usd_cost_cents: int
    latency_ms: int


class ApiTestGenerationService:
    def __init__(self, session: Session, agent: ApiTesterAgent) -> None:
        self._session = session
        self._agent = agent
        self._audit = AuditService(session)

    async def generate(
        self,
        *,
        test_plan_id: UUID,
        context: RequestContext,
    ) -> ApiTestGenerationOutput:
        plan = self._session.get(TestPlan, test_plan_id)
        if plan is None:
            raise ResourceNotFoundError("test_plan", test_plan_id)

        requirement = self._session.get(Requirement, plan.requirement_id)
        if requirement is None or requirement.type is not RequirementType.OPENAPI:
            raise NoOpenApiRequirementError(
                "ApiTester requires the upstream requirement to be of type=openapi"
            )

        cases = self._fetch_cases(plan.id)
        case_payloads = [self._case_to_dict(c) for c in cases]

        output = await self._agent.generate(
            ApiTesterInput(
                test_plan_id=plan.id,
                workspace_id=plan.workspace_id,
                module_name=_module_name_for(plan),
                openapi_summary={
                    "title": requirement.parsed.get("title"),
                    "version": requirement.parsed.get("version"),
                    "endpoints": requirement.parsed.get("endpoints", []),
                },
                test_cases=case_payloads,
                base_url_default=None,
                correlation_id=context.correlation_id,
            )
        )

        cases_updated = self._attach_generated_to_cases(
            cases=cases,
            suite=output.suite,
        )

        cost_cents = round(float(output.usage.usd_cost) * 100)
        self._audit.record(
            context=context,
            action="api_tests.generated",
            resource_type="test_plan",
            resource_id=plan.id,
            payload={
                "framework": output.suite.framework,
                "module_name": output.suite.module_name,
                "tests_generated": len(output.suite.tests),
                "cases_updated": cases_updated,
                "model": output.usage.model,
                "prompt_version": output.prompt_version,
                "usd_cost": str(output.usage.usd_cost),
            },
        )

        return ApiTestGenerationOutput(
            test_plan_id=plan.id,
            suite=output.suite,
            cases_updated=cases_updated,
            usd_cost_cents=cost_cents,
            latency_ms=output.usage.latency_ms,
        )

    # --- internals --------------------------------------------------------------

    def _fetch_cases(self, test_plan_id: UUID) -> Sequence[TestCase]:
        return list(
            self._session.scalars(
                select(TestCase)
                .where(TestCase.test_plan_id == test_plan_id)
                .order_by(TestCase.created_at.asc())
            ).all()
        )

    @staticmethod
    def _case_to_dict(case: TestCase) -> dict[str, Any]:
        return {
            "title": case.title,
            "type": case.type.value,
            "priority": case.priority.value,
            "preconditions": list(case.preconditions),
            "steps": list(case.steps),
            "expected_result": case.expected_result,
            "automation_candidate": case.automation_candidate,
        }

    def _attach_generated_to_cases(
        self,
        *,
        cases: Sequence[TestCase],
        suite: GeneratedTestSuite,
    ) -> int:
        by_title = {c.title.lower(): c for c in cases}
        updated = 0
        for generated in suite.tests:
            target = by_title.get(generated.test_case_title.lower())
            if target is None:
                continue
            metadata = dict(target.metadata_json or {})
            metadata["generated_code"] = {
                "framework": suite.framework,
                "module_name": suite.module_name,
                "function_name": generated.function_name,
                "method": generated.method,
                "path": generated.path,
                "expected_status": generated.expected_status,
                "is_negative": generated.is_negative,
                "requires_auth": generated.requires_auth,
            }
            target.metadata_json = metadata
            updated += 1
        if updated:
            self._session.flush()
        return updated


def _module_name_for(plan: TestPlan) -> str:
    return "test_" + plan.id.hex[:12]
