"""API-test generation routes — Story 1.4."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aqao_agents.api_tester import ApiTesterAgent
from aqao_api.agents_factory import get_api_tester_agent
from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.schemas.api_test import (
    ApiTestSuiteResponse,
    GeneratedTestSummary,
)
from aqao_api.services.api_test_generation import (
    ApiTestGenerationService,
    NoOpenApiRequirementError,
)
from aqao_api.services.errors import ResourceNotFoundError

router = APIRouter(
    prefix="/api/v1/test-plans/{test_plan_id}/api-tests",
    tags=["test-plans"],
)


def _service(
    session: Session = Depends(tenant_scoped_session),
    agent: ApiTesterAgent = Depends(get_api_tester_agent),
) -> ApiTestGenerationService:
    return ApiTestGenerationService(session, agent)


@router.post(
    "/generate",
    response_model=ApiTestSuiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate pytest+httpx code from a test plan's OpenAPI requirement",
)
async def generate_api_tests(
    test_plan_id: UUID,
    service: ApiTestGenerationService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> ApiTestSuiteResponse:
    try:
        out = await service.generate(test_plan_id=test_plan_id, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="test plan not found",
        ) from exc
    except NoOpenApiRequirementError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ApiTestSuiteResponse(
        test_plan_id=out.test_plan_id,
        framework=out.suite.framework,
        module_name=out.suite.module_name,
        source_code=out.suite.source_code,
        tests=[
            GeneratedTestSummary(
                test_case_title=t.test_case_title,
                function_name=t.function_name,
                method=t.method,
                path=t.path,
                expected_status=t.expected_status,
                is_negative=t.is_negative,
                requires_auth=t.requires_auth,
            )
            for t in out.suite.tests
        ],
        cases_updated=out.cases_updated,
        usd_cost_cents=out.usd_cost_cents,
        latency_ms=out.latency_ms,
    )
