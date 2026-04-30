"""Approval routes — Story 2.1.3.

PRD §13 surface: ``/api/v1/approvals``. The Phase-2 admin UI hits these
endpoints to fetch the queue, drill in on a single ask, and post a
decision. Slack/email approval links eventually deep-link here too.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from qaforge_api.auth import (
    Permission,
    emit_resource_miss,
    require_permission,
)
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import ApprovalState
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalListResponse,
    ApprovalRequestResponse,
)
from qaforge_api.services.approval import ApprovalService
from qaforge_api.services.errors import (
    InvalidStateError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _service(session: Session = Depends(tenant_scoped_session)) -> ApprovalService:
    return ApprovalService(session)


@router.get(
    "",
    response_model=ApprovalListResponse,
    summary="List approval requests, newest first.",
)
def list_approvals(
    state: list[str] | None = Query(default=None),
    workspace_id: UUID | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: ApprovalService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.APPROVAL_VIEW)),
) -> ApprovalListResponse:
    states: list[ApprovalState] | None = None
    if state:
        try:
            states = [ApprovalState(s) for s in state]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown approval state: {exc}",
            ) from exc

    rows = service.list_requests(
        states=states,
        workspace_id=workspace_id,
        event_type=event_type,
        limit=limit,
    )
    return ApprovalListResponse(items=[ApprovalRequestResponse.model_validate(r) for r in rows])


@router.get(
    "/{request_id}",
    response_model=ApprovalRequestResponse,
    summary="Fetch a single approval request.",
)
def get_approval(
    request_id: UUID,
    service: ApprovalService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.APPROVAL_VIEW)),
) -> ApprovalRequestResponse:
    try:
        row = service.get(request_id=request_id)
    except ResourceNotFoundError as exc:
        emit_resource_miss(
            context=context,
            resource_type="approval_request",
            resource_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="approval request not found",
        ) from exc
    return ApprovalRequestResponse.model_validate(row)


@router.post(
    "/{request_id}/approve",
    response_model=ApprovalRequestResponse,
    summary="Approve a pending request.",
)
def approve(
    request_id: UUID,
    payload: ApprovalDecisionRequest,
    service: ApprovalService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.APPROVAL_DECIDE)),
) -> ApprovalRequestResponse:
    return _decide(
        method=service.approve,
        request_id=request_id,
        comment=payload.comment,
        context=context,
    )


@router.post(
    "/{request_id}/reject",
    response_model=ApprovalRequestResponse,
    summary="Reject a pending request.",
)
def reject(
    request_id: UUID,
    payload: ApprovalDecisionRequest,
    service: ApprovalService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.APPROVAL_DECIDE)),
) -> ApprovalRequestResponse:
    return _decide(
        method=service.reject,
        request_id=request_id,
        comment=payload.comment,
        context=context,
    )


@router.post(
    "/{request_id}/cancel",
    response_model=ApprovalRequestResponse,
    summary="Cancel a pending request (e.g. workflow gave up).",
)
def cancel(
    request_id: UUID,
    payload: ApprovalDecisionRequest,
    service: ApprovalService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.APPROVAL_DECIDE)),
) -> ApprovalRequestResponse:
    return _decide(
        method=service.cancel,
        request_id=request_id,
        comment=payload.comment,
        context=context,
    )


def _decide(
    *,
    method: object,
    request_id: UUID,
    comment: str | None,
    context: RequestContext,
) -> ApprovalRequestResponse:
    try:
        row = method(  # type: ignore[operator]
            request_id=request_id, context=context, comment=comment
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="approval request not found",
        ) from exc
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return ApprovalRequestResponse.model_validate(row)
