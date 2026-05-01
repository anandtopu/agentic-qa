"""UI-test generation routes — Story 1.5."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aqao_agents.ui_tester import UiTesterAgent
from aqao_api.agents_factory import get_ui_tester_agent
from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.schemas.ui_test import (
    FragilityFindingResponse,
    GeneratedUiTestSummary,
    UiTestSpecResponse,
)
from aqao_api.services.errors import ResourceNotFoundError
from aqao_api.services.ui_test_generation import (
    NoUiCasesError,
    UiTestGenerationService,
)

router = APIRouter(
    prefix="/api/v1/test-plans/{test_plan_id}/ui-tests",
    tags=["test-plans"],
)


def _service(
    session: Session = Depends(tenant_scoped_session),
    agent: UiTesterAgent = Depends(get_ui_tester_agent),
) -> UiTestGenerationService:
    return UiTestGenerationService(session, agent)


@router.post(
    "/generate",
    response_model=UiTestSpecResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Playwright TS spec from a test plan's UI cases",
)
async def generate_ui_tests(
    test_plan_id: UUID,
    service: UiTestGenerationService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> UiTestSpecResponse:
    try:
        out = await service.generate(test_plan_id=test_plan_id, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="test plan not found",
        ) from exc
    except NoUiCasesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UiTestSpecResponse(
        test_plan_id=out.test_plan_id,
        framework=out.spec.framework,
        spec_filename=out.spec.spec_filename,
        source_code=out.spec.source_code,
        tests=[
            GeneratedUiTestSummary(
                test_case_title=t.test_case_title,
                title=t.title,
                journey_steps=list(t.journey_steps),
                expected_outcome=t.expected_outcome,
                requires_auth=t.requires_auth,
            )
            for t in out.spec.tests
        ],
        fragility_findings=[
            FragilityFindingResponse(
                line_number=f.line_number,
                snippet=f.snippet,
                rule=f.rule,
                severity=f.severity,
                suggestion=f.suggestion,
            )
            for f in out.fragility.findings
        ],
        cases_updated=out.cases_updated,
        usd_cost_cents=out.usd_cost_cents,
        latency_ms=out.latency_ms,
    )
