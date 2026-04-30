"""Model lifecycle routes — Story 6.2.1.

Surface for the Phase-6 model lifecycle ritual:

* ``POST   /api/v1/model-registry`` — register a candidate.
* ``POST   /api/v1/model-registry/{id}/scorecard`` — attach an eval
  scorecard to a candidate.
* ``POST   /api/v1/model-registry/{id}/decision`` — record go / no_go.
* ``POST   /api/v1/model-registry/{id}/deprecate`` — schedule sunset.
* ``GET    /api/v1/model-registry`` — list (filterable by status).
* ``GET    /api/v1/model-registry/awaiting-decision`` — SLA report.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from qaforge_api.auth import Permission, require_permission
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    ModelDecision,
    ModelLifecycleStatus,
    ModelRegistryEntry,
)
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.model_registry import (
    AttachScorecardRequest,
    AwaitingDecisionEntry,
    AwaitingDecisionResponse,
    ModelDecisionRequest,
    ModelDecisionValue,
    ModelDeprecationRequest,
    ModelLifecycleStatusValue,
    ModelRegisterRequest,
    ModelRegistryEntryResponse,
    ModelRegistryListResponse,
)
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError
from qaforge_api.services.model_lifecycle import (
    InvalidLifecycleTransitionError,
    ModelLifecycleService,
)

router = APIRouter(prefix="/api/v1/model-registry", tags=["model-registry"])


def _service(
    session: Session = Depends(tenant_scoped_session),
) -> ModelLifecycleService:
    return ModelLifecycleService(session, audit=AuditService(session))


def _to_response(row: ModelRegistryEntry) -> ModelRegistryEntryResponse:
    return ModelRegistryEntryResponse(
        id=row.id,
        provider=row.provider,
        model_id=row.model_id,
        family=row.family,
        released_at=row.released_at,
        status=ModelLifecycleStatusValue(row.status),
        eval_scorecard_id=row.eval_scorecard_id,
        eval_scorecard_path=row.eval_scorecard_path,
        decision=ModelDecisionValue(row.decision) if row.decision else None,
        decision_rationale=row.decision_rationale,
        decision_at=row.decision_at,
        decided_by_user_id=row.decided_by_user_id,
        deprecation_at=row.deprecation_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "",
    response_model=ModelRegistryEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a candidate model release",
)
def register_model(
    payload: ModelRegisterRequest,
    service: ModelLifecycleService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.WORKSPACE_EDIT)),
) -> ModelRegistryEntryResponse:
    row = service.register(
        context=context,
        provider=payload.provider,
        model_id=payload.model_id,
        family=payload.family,
        released_at=payload.released_at,
    )
    return _to_response(row)


@router.post(
    "/{entry_id}/scorecard",
    response_model=ModelRegistryEntryResponse,
    summary="Attach an eval scorecard to a candidate",
)
def attach_scorecard(
    entry_id: UUID,
    payload: AttachScorecardRequest,
    service: ModelLifecycleService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.EVAL_RUN)),
) -> ModelRegistryEntryResponse:
    try:
        row = service.attach_scorecard(
            context=context,
            entry_id=entry_id,
            eval_scorecard_id=payload.eval_scorecard_id,
            eval_scorecard_path=payload.eval_scorecard_path,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model_registry not found") from exc
    return _to_response(row)


@router.post(
    "/{entry_id}/decision",
    response_model=ModelRegistryEntryResponse,
    summary="Record go/no-go on a candidate",
)
def record_decision(
    entry_id: UUID,
    payload: ModelDecisionRequest,
    service: ModelLifecycleService = Depends(_service),
    context: RequestContext = Depends(
        require_permission(Permission.EVAL_BASELINE_PROMOTE)
    ),
) -> ModelRegistryEntryResponse:
    try:
        row = service.record_decision(
            context=context,
            entry_id=entry_id,
            decision=ModelDecision(payload.decision.value),
            rationale=payload.rationale,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model_registry not found") from exc
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _to_response(row)


@router.post(
    "/{entry_id}/deprecate",
    response_model=ModelRegistryEntryResponse,
    summary="Schedule sunset for a previously-pinned model",
)
def deprecate_model(
    entry_id: UUID,
    payload: ModelDeprecationRequest,
    service: ModelLifecycleService = Depends(_service),
    context: RequestContext = Depends(
        require_permission(Permission.EVAL_BASELINE_PROMOTE)
    ),
) -> ModelRegistryEntryResponse:
    try:
        row = service.deprecate(
            context=context,
            entry_id=entry_id,
            deprecation_at=payload.deprecation_at,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model_registry not found") from exc
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _to_response(row)


@router.get(
    "",
    response_model=ModelRegistryListResponse,
    summary="List registered models for the current tenant",
)
def list_models(
    status_filter: ModelLifecycleStatusValue | None = Query(default=None, alias="status"),
    service: ModelLifecycleService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> ModelRegistryListResponse:
    status_enum = (
        ModelLifecycleStatus(status_filter.value) if status_filter is not None else None
    )
    rows = service.list_entries(tenant_id=context.tenant_id, status=status_enum)
    return ModelRegistryListResponse(items=[_to_response(r) for r in rows])


@router.get(
    "/awaiting-decision",
    response_model=AwaitingDecisionResponse,
    summary="Candidates whose go/no-go is overdue per the configurable SLA",
)
def awaiting_decision(
    sla_days: int = Query(default=14, ge=1, le=365),
    service: ModelLifecycleService = Depends(_service),
    context: RequestContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> AwaitingDecisionResponse:
    rows = service.awaiting_decision(
        tenant_id=context.tenant_id,
        sla=timedelta(days=sla_days),
    )
    items = [
        AwaitingDecisionEntry(
            entry=_to_response(row.entry),
            age_days=row.age_days,
            sla_breached=row.sla_breached,
        )
        for row in rows
    ]
    return AwaitingDecisionResponse(
        sla_days=sla_days,
        items=items,
        breach_count=sum(1 for item in items if item.sla_breached),
    )


__all__ = ["router"]
