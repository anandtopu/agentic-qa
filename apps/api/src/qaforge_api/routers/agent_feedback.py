"""Agent-feedback routes — Story 6.3.1.

Surface for the in-product thumbs up/down loop:

* ``POST /api/v1/feedback`` — record a single rating.
* ``GET  /api/v1/workspaces/{id}/feedback`` — filtered ledger view.
* ``GET  /api/v1/workspaces/{id}/feedback/low-rated-review`` — the
  rolling-window summary the eng-lead reviews every Monday.
* ``POST /api/v1/feedback/{feedback_id}/convert-to-eval`` — promote
  one negatively-rated row into a regression case under
  ``packages/eval/datasets/<agent>/feedback_cases.jsonl``.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from qaforge_api.auth import Permission, require_permission
from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.config import get_settings
from qaforge_api.db.models import AgentFeedback, FeedbackRating
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.agent_feedback import (
    EvalConversionResult,
    FeedbackCreateRequest,
    FeedbackListResponse,
    FeedbackRatingValue,
    FeedbackResponse,
    LowRatedReviewEntry,
    LowRatedReviewResponse,
)
from qaforge_api.services.agent_feedback import (
    AgentFeedbackService,
    FeedbackNotConvertibleError,
)
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError

router = APIRouter(prefix="/api/v1", tags=["feedback"])


def _service(
    session: Session = Depends(tenant_scoped_session),
) -> AgentFeedbackService:
    settings = get_settings()
    return AgentFeedbackService(
        session,
        audit=AuditService(session),
        eval_dataset_dir=Path(settings.eval_dataset_dir),
    )


def _to_response(row: AgentFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        agent_kind=row.agent_kind,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        rating=FeedbackRatingValue(row.rating),
        comment=row.comment,
        submitted_by_user_id=row.submitted_by_user_id,
        submitted_at=row.submitted_at,
        eval_case_id=row.eval_case_id,
        eval_case_path=row.eval_case_path,
        converted_at=row.converted_at,
    )


class ConvertToEvalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected: dict[str, Any] | None = Field(
        default=None,
        description="Optional operator-supplied 'what should the agent have produced'.",
    )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a thumbs up/down on an agent output",
)
def create_feedback(
    payload: FeedbackCreateRequest,
    service: AgentFeedbackService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> FeedbackResponse:
    row = service.record(
        context=context,
        workspace_id=payload.workspace_id,
        agent_kind=payload.agent_kind,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        rating=FeedbackRating(payload.rating.value),
        comment=payload.comment,
    )
    return _to_response(row)


@router.get(
    "/workspaces/{workspace_id}/feedback",
    response_model=FeedbackListResponse,
    summary="List recorded agent feedback for a workspace",
)
def list_feedback(
    workspace_id: UUID,
    agent_kind: str | None = Query(default=None),
    rating: FeedbackRatingValue | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    service: AgentFeedbackService = Depends(_service),
    _: RequestContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> FeedbackListResponse:
    rating_enum = FeedbackRating(rating.value) if rating is not None else None
    rows = service.query(
        workspace_id=workspace_id,
        agent_kind=agent_kind,
        rating=rating_enum,
        limit=limit,
    )
    return FeedbackListResponse(items=[_to_response(r) for r in rows])


@router.get(
    "/workspaces/{workspace_id}/feedback/low-rated-review",
    response_model=LowRatedReviewResponse,
    summary="Weekly low-rated review summary (Epic 6.3 ritual)",
)
def low_rated_review(
    workspace_id: UUID,
    window_days: int = Query(default=7, ge=1, le=90),
    service: AgentFeedbackService = Depends(_service),
    _: RequestContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> LowRatedReviewResponse:
    review = service.weekly_review(
        workspace_id=workspace_id,
        window=timedelta(days=window_days),
    )
    return LowRatedReviewResponse(
        workspace_id=review.workspace_id,
        window_days=review.window_days,
        since=review.since,
        overall_total=review.overall_total,
        overall_down_count=review.overall_down_count,
        overall_conversion_rate=review.overall_conversion_rate,
        by_agent=[
            LowRatedReviewEntry(
                agent_kind=s.agent_kind,
                total_feedback=s.total_feedback,
                down_count=s.down_count,
                up_count=s.up_count,
                down_rate=s.down_rate,
                pending_conversion=s.pending_conversion,
                converted=s.converted,
                conversion_rate=s.conversion_rate,
            )
            for s in review.by_agent
        ],
        pending_items=[_to_response(r) for r in review.pending_items],
    )


@router.post(
    "/feedback/{feedback_id}/convert-to-eval",
    response_model=EvalConversionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Promote a negatively-rated feedback row into a regression eval case",
)
def convert_to_eval(
    feedback_id: UUID,
    payload: ConvertToEvalRequest | None = None,
    service: AgentFeedbackService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.EVAL_RUN)),
) -> EvalConversionResult:
    try:
        outcome = service.convert_to_eval_case(
            context=context,
            feedback_id=feedback_id,
            expected=(payload.expected if payload is not None else None),
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent_feedback not found",
        ) from exc
    except FeedbackNotConvertibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    row = outcome.feedback
    converted_at = row.converted_at
    if converted_at is None:  # pragma: no cover  — service always sets this
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="conversion did not stamp converted_at",
        )
    return EvalConversionResult(
        feedback_id=row.id,
        eval_case_id=outcome.append_result.case_id,
        eval_case_path=outcome.append_result.relative_path,
        agent_kind=row.agent_kind,
        converted_at=converted_at,
    )


__all__ = ["router"]
