"""UiTestGenerationService — Story 1.5.

Mirror of :class:`ApiTestGenerationService` for UI tests. Calls the
:class:`UiTesterAgent`, persists generated TS into each matching test
case's ``metadata_json``, and runs the fragility analyser to attach a
report to the audit payload.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_agents.ui_tester import (
    FragilityReport,
    GeneratedUiTestSpec,
    UiTesterAgent,
    UiTesterInput,
)
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import TestCase, TestPlan, Workspace
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError, ServiceError


class NoUiCasesError(ServiceError):
    """Raised when the test plan has no UI-tier cases to generate."""


@dataclass(slots=True)
class UiTestGenerationOutput:
    test_plan_id: UUID
    spec: GeneratedUiTestSpec
    fragility: FragilityReport
    cases_updated: int
    usd_cost_cents: int
    latency_ms: int


class UiTestGenerationService:
    def __init__(self, session: Session, agent: UiTesterAgent) -> None:
        self._session = session
        self._agent = agent
        self._audit = AuditService(session)

    async def generate(
        self,
        *,
        test_plan_id: UUID,
        context: RequestContext,
    ) -> UiTestGenerationOutput:
        plan = self._session.get(TestPlan, test_plan_id)
        if plan is None:
            raise ResourceNotFoundError("test_plan", test_plan_id)

        workspace = self._session.get(Workspace, plan.workspace_id)
        workspace_summary: dict[str, Any] = (
            {
                "name": workspace.name,
                "application_type": workspace.application_type.value,
                "repo_url": workspace.repo_url,
                "default_branch": workspace.default_branch,
            }
            if workspace is not None
            else {}
        )

        cases = self._fetch_cases(plan.id)
        case_payloads = [self._case_to_dict(c) for c in cases]
        relevant = UiTesterAgent.filter_relevant_cases(case_payloads)
        if not relevant:
            raise NoUiCasesError("test plan has no UI-tier cases (ui/smoke/regression/integration)")

        output = await self._agent.generate(
            UiTesterInput(
                test_plan_id=plan.id,
                workspace_id=plan.workspace_id,
                spec_filename=_spec_filename_for(plan),
                workspace_summary=workspace_summary,
                test_cases=case_payloads,
                base_url_default=None,
                correlation_id=context.correlation_id,
            )
        )

        cases_updated = self._attach_generated(
            cases=cases,
            spec=output.spec,
        )

        cost_cents = round(float(output.usage.usd_cost) * 100)
        self._audit.record(
            context=context,
            action="ui_tests.generated",
            resource_type="test_plan",
            resource_id=plan.id,
            payload={
                "framework": output.spec.framework,
                "spec_filename": output.spec.spec_filename,
                "tests_generated": len(output.spec.tests),
                "cases_updated": cases_updated,
                "fragility_findings": len(output.fragility_report.findings),
                "fragility_summary": output.fragility_report.summary(),
                "model": output.usage.model,
                "prompt_version": output.prompt_version,
                "usd_cost": str(output.usage.usd_cost),
            },
        )

        return UiTestGenerationOutput(
            test_plan_id=plan.id,
            spec=output.spec,
            fragility=output.fragility_report,
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

    def _attach_generated(
        self,
        *,
        cases: Sequence[TestCase],
        spec: GeneratedUiTestSpec,
    ) -> int:
        by_title = {c.title.lower(): c for c in cases}
        updated = 0
        for generated in spec.tests:
            target = by_title.get(generated.test_case_title.lower())
            if target is None:
                continue
            metadata = dict(target.metadata_json or {})
            metadata["generated_ui_spec"] = {
                "framework": spec.framework,
                "spec_filename": spec.spec_filename,
                "title": generated.title,
                "journey_steps": list(generated.journey_steps),
                "expected_outcome": generated.expected_outcome,
                "requires_auth": generated.requires_auth,
            }
            target.metadata_json = metadata
            updated += 1
        if updated:
            self._session.flush()
        return updated


def _spec_filename_for(plan: TestPlan) -> str:
    return f"plan_{plan.id.hex[:12]}.spec.ts"
