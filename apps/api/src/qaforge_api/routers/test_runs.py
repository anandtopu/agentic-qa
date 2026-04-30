"""Test run routes — Story 1.6."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.db.models.test_run import TestRunState
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.test_run import (
    AgentTaskResponse,
    TestRunListResponse,
    TestRunResponse,
    TestRunStartRequest,
    TestRunStartResponse,
)
from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)
from qaforge_api.services.test_run import (
    TestRunService,
    default_pr_analysis_graph,
)

flat = APIRouter(prefix="/api/v1/test-runs", tags=["test-runs"])
per_workspace = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/test-runs",
    tags=["test-runs"],
)


def _service(session: Session = Depends(tenant_scoped_session)) -> TestRunService:
    return TestRunService(session)


@flat.post(
    "",
    response_model=TestRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a test run from a test plan",
)
async def start_test_run(
    payload: TestRunStartRequest,
    service: TestRunService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> TestRunStartResponse:
    try:
        out = await service.start(
            test_plan_id=payload.test_plan_id,
            graph=default_pr_analysis_graph(),
            idempotency_key=payload.idempotency_key,
            context=context,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="test plan not found",
        ) from exc
    except DuplicateResourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return TestRunStartResponse(
        run=TestRunResponse.model_validate(out.test_run),
        final_state=TestRunState(out.final_state.value),
        steps_executed=out.steps_executed,
        paused=out.paused,
    )


@flat.get(
    "/{test_run_id}",
    response_model=TestRunResponse,
    summary="Get a test run",
)
def get_test_run(
    test_run_id: UUID,
    service: TestRunService = Depends(_service),
) -> TestRunResponse:
    try:
        run = service.get(test_run_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="test run not found"
        ) from exc
    return TestRunResponse.model_validate(run)


@flat.get(
    "/{test_run_id}/steps",
    response_model=list[AgentTaskResponse],
    summary="List the agent tasks executed by a test run",
)
def list_test_run_steps(
    test_run_id: UUID,
    service: TestRunService = Depends(_service),
) -> list[AgentTaskResponse]:
    try:
        steps = service.list_steps(test_run_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="test run not found"
        ) from exc
    return [AgentTaskResponse.model_validate(s) for s in steps]


@per_workspace.get(
    "",
    response_model=TestRunListResponse,
    summary="List test runs for a workspace",
)
def list_workspace_test_runs(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: TestRunService = Depends(_service),
) -> TestRunListResponse:
    runs = service.list_for_workspace(workspace_id=workspace_id, limit=limit, offset=offset)
    return TestRunListResponse(
        runs=[TestRunResponse.model_validate(r) for r in runs],
        limit=limit,
        offset=offset,
    )
