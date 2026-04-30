"""Test plan routes — Story 1.3."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from qaforge_agents.planner import PlannerAgent
from qaforge_api.agents_factory import get_planner_agent
from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.test_plan import (
    TestPlanGenerateRequest,
    TestPlanListResponse,
    TestPlanResponse,
)
from qaforge_api.services.errors import ResourceNotFoundError
from qaforge_api.services.test_plan import TestPlanService

flat = APIRouter(prefix="/api/v1/test-plans", tags=["test-plans"])
per_workspace = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/test-plans",
    tags=["test-plans"],
)


def _service(
    session: Session = Depends(tenant_scoped_session),
    planner: PlannerAgent = Depends(get_planner_agent),
) -> TestPlanService:
    return TestPlanService(session, planner)


@flat.post(
    "",
    response_model=TestPlanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a test plan from a requirement",
)
async def generate_test_plan(
    payload: TestPlanGenerateRequest,
    service: TestPlanService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> TestPlanResponse:
    try:
        plan = await service.generate(
            requirement_id=payload.requirement_id,
            context=context,
            existing_test_titles=payload.existing_test_titles,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="requirement not found",
        ) from exc
    return TestPlanResponse.model_validate(plan)


@flat.get(
    "/{test_plan_id}",
    response_model=TestPlanResponse,
    summary="Get a test plan by id",
)
def get_test_plan(
    test_plan_id: UUID,
    service: TestPlanService = Depends(_service),
) -> TestPlanResponse:
    try:
        plan = service.get(test_plan_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="test plan not found",
        ) from exc
    return TestPlanResponse.model_validate(plan)


@per_workspace.get(
    "",
    response_model=TestPlanListResponse,
    summary="List test plans for a workspace",
)
def list_workspace_plans(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: TestPlanService = Depends(_service),
) -> TestPlanListResponse:
    plans = service.list_for_workspace(workspace_id=workspace_id, limit=limit, offset=offset)
    return TestPlanListResponse(
        test_plans=[TestPlanResponse.model_validate(p) for p in plans],
        limit=limit,
        offset=offset,
    )
