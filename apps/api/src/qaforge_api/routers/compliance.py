"""Compliance routes — Stories 6.5.1 + 6.5.2.

* ``POST /api/v1/compliance/retention/sweep`` — owner-only retention
  sweep (with optional ``dry_run`` for the Monday preview).
* ``GET  /api/v1/compliance/access-review`` — admin-visible access
  review snapshot for the quarterly SOC-2 ritual.

Audit events are compliance-locked (7-year retention) and the
sweep service refuses to delete them — see ``services/retention.py``.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from qaforge_api.auth import Permission, require_permission
from qaforge_api.auth.context import RequestContext
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.compliance import (
    AccessReviewEntryResponse,
    AccessReviewSnapshotResponse,
    ClassSweepResultResponse,
    RetentionSweepRequest,
    SweepReportResponse,
)
from qaforge_api.services.access_review import AccessReviewService
from qaforge_api.services.audit import AuditService
from qaforge_api.services.retention import RetentionSweepService

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


def _retention_service(
    session: Session = Depends(tenant_scoped_session),
) -> RetentionSweepService:
    return RetentionSweepService(session, audit=AuditService(session))


def _access_review_service(
    session: Session = Depends(tenant_scoped_session),
) -> AccessReviewService:
    return AccessReviewService(session)


@router.post(
    "/retention/sweep",
    response_model=SweepReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the data-class retention sweep (Story 6.5.1)",
)
def run_retention_sweep(
    payload: RetentionSweepRequest | None = None,
    service: RetentionSweepService = Depends(_retention_service),
    context: RequestContext = Depends(
        require_permission(Permission.WORKSPACE_DELETE)
    ),
) -> SweepReportResponse:
    dry_run = payload.dry_run if payload is not None else False
    report = service.sweep(context=context, dry_run=dry_run)
    return SweepReportResponse(
        started_at=report.started_at,
        finished_at=report.finished_at,
        dry_run=report.dry_run,
        total_deleted=report.total_deleted,
        total_would_delete=report.total_would_delete,
        classes=[
            ClassSweepResultResponse(
                name=c.name,
                cutoff=c.cutoff,
                default_days=c.default_days,
                compliance_locked=c.compliance_locked,
                deleted=c.deleted,
                would_delete=c.would_delete,
                skipped_reason=c.skipped_reason,
            )
            for c in report.classes
        ],
    )


@router.get(
    "/access-review",
    response_model=AccessReviewSnapshotResponse,
    summary="Quarterly access review snapshot (Story 6.5.2)",
)
def access_review(
    window_days: int = Query(default=90, ge=1, le=365),
    service: AccessReviewService = Depends(_access_review_service),
    context: RequestContext = Depends(require_permission(Permission.AUDIT_VIEW)),
) -> AccessReviewSnapshotResponse:
    snapshot = service.snapshot(
        tenant_id=context.tenant_id,
        window=timedelta(days=window_days),
    )
    return AccessReviewSnapshotResponse(
        tenant_id=snapshot.tenant_id,
        window_days=snapshot.window_days,
        since=snapshot.since,
        entries=[
            AccessReviewEntryResponse(
                user_id=e.user_id,
                email=e.email,
                name=e.name,
                role=e.role,
                last_seen_at=e.last_seen_at,
                recent_action_count=e.recent_action_count,
                is_dormant=e.is_dormant,
            )
            for e in snapshot.entries
        ],
        dormant_count=snapshot.dormant_count,
    )


__all__ = ["router"]
