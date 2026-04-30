"""Failure-classification routes — Story 1.7."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from qaforge_agents.classifier import FailureClassifierAgent
from qaforge_api.agents_factory import get_failure_classifier_agent
from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.failure_classification import (
    ClassifyFailuresRequest,
    ClassifyFailuresResponse,
    FailureClassificationResponse,
)
from qaforge_api.services.errors import ResourceNotFoundError
from qaforge_api.services.failure_classification import (
    FailureClassificationService,
)

router = APIRouter(
    prefix="/api/v1/test-runs/{test_run_id}/failures",
    tags=["failures"],
)


def _service(
    session: Session = Depends(tenant_scoped_session),
    agent: FailureClassifierAgent = Depends(get_failure_classifier_agent),
) -> FailureClassificationService:
    return FailureClassificationService(session, agent)


@router.post(
    "/classify",
    response_model=ClassifyFailuresResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Classify a batch of failure signals against PRD §9.8",
)
async def classify_failures(
    test_run_id: UUID,
    payload: ClassifyFailuresRequest,
    service: FailureClassificationService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> ClassifyFailuresResponse:
    try:
        out = await service.classify(
            test_run_id=test_run_id,
            signals=payload.signals,
            context=context,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="test run not found",
        ) from exc
    return ClassifyFailuresResponse(
        test_run_id=out.test_run_id,
        classifications=[
            FailureClassificationResponse.model_validate(r) for r in out.classifications
        ],
        heuristic_ratio=out.heuristic_ratio,
        llm_call_count=out.llm_call_count,
        total_usd_cost_cents=out.total_usd_cost_cents,
    )


@router.get(
    "",
    response_model=list[FailureClassificationResponse],
    summary="List recorded failure classifications for a test run",
)
def list_failures(
    test_run_id: UUID,
    service: FailureClassificationService = Depends(_service),
) -> list[FailureClassificationResponse]:
    rows = service.list_for_run(test_run_id)
    return [FailureClassificationResponse.model_validate(r) for r in rows]
