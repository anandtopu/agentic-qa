"""Audit timeline + export routes — Story 2.4.2."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.config import get_settings
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.audit import AuditEventResponse, AuditQueryResponse
from qaforge_api.services.audit_query import (
    AuditQueryService,
    VerifiedAuditEvent,
)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


def _service(session: Session = Depends(tenant_scoped_session)) -> AuditQueryService:
    secret = get_settings().audit_hmac_key
    return AuditQueryService(
        session,
        hmac_key=secret.get_secret_value() if secret is not None else "",
    )


def _to_response(events: list[VerifiedAuditEvent]) -> list[AuditEventResponse]:
    return [
        AuditEventResponse(
            id=ve.event.id,
            tenant_id=ve.event.tenant_id,
            actor_user_id=ve.event.actor_user_id,
            action=ve.event.action,
            resource_type=ve.event.resource_type,
            resource_id=ve.event.resource_id,
            payload=dict(ve.event.payload or {}),
            correlation_id=ve.event.correlation_id,
            signature=ve.event.signature,
            signature_status=ve.status.value,
            created_at=ve.event.created_at,
        )
        for ve in events
    ]


@router.get(
    "",
    response_model=AuditQueryResponse,
    summary="Filterable audit timeline (tenant-scoped, signature-verified)",
)
def query_audit(
    actor_user_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=100),
    resource_id: str | None = Query(default=None, max_length=200),
    action: str | None = Query(default=None, max_length=100),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: AuditQueryService = Depends(_service),
    _ctx: RequestContext = Depends(require_request_context),
) -> AuditQueryResponse:
    rows = service.query(
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return AuditQueryResponse(
        events=_to_response(rows),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/export.csv",
    response_class=PlainTextResponse,
    summary="Export the filtered audit timeline as CSV",
)
def export_csv(
    actor_user_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=100),
    resource_id: str | None = Query(default=None, max_length=200),
    action: str | None = Query(default=None, max_length=100),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
    service: AuditQueryService = Depends(_service),
    _ctx: RequestContext = Depends(require_request_context),
) -> PlainTextResponse:
    rows = service.query(
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    csv_text = service.export_csv(rows)
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit.csv"'},
    )


@router.get(
    "/export.json",
    response_class=PlainTextResponse,
    summary="Export the filtered audit timeline as JSON",
)
def export_json(
    actor_user_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=100),
    resource_id: str | None = Query(default=None, max_length=200),
    action: str | None = Query(default=None, max_length=100),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
    service: AuditQueryService = Depends(_service),
    _ctx: RequestContext = Depends(require_request_context),
) -> PlainTextResponse:
    rows = service.query(
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    json_text = service.export_json(rows)
    return PlainTextResponse(
        content=json_text,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="audit.json"'},
    )
