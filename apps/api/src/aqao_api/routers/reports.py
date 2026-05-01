"""Evidence-report routes — Story 1.8."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.evidence import EvidenceStore, get_evidence_store
from aqao_api.schemas.evidence_report import (
    EvidenceReportResponse,
    GenerateReportRequest,
)
from aqao_api.services.errors import ResourceNotFoundError
from aqao_api.services.evidence_report import (
    EvidenceReportService,
    GeneratedReport,
)

router = APIRouter(tags=["reports"])


def _service(
    session: Session = Depends(tenant_scoped_session),
    store: EvidenceStore = Depends(get_evidence_store),
) -> EvidenceReportService:
    return EvidenceReportService(session, evidence_store=store)


def _to_response(report: GeneratedReport) -> EvidenceReportResponse:
    return EvidenceReportResponse(
        artifact_id=report.artifact.id,
        test_run_id=report.artifact.test_run_id,
        sha256=report.artifact.sha256,
        size_bytes=report.artifact.size_bytes,
        storage_key=report.artifact.storage_key,
        markdown=report.markdown,
        signed_url=report.signed_url,
        signed_url_expires_at=report.signed_url_expires_at,
    )


@router.post(
    "/api/v1/test-runs/{test_run_id}/reports",
    response_model=EvidenceReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Render and persist a Markdown evidence report",
)
async def generate_report(
    test_run_id: UUID,
    payload: GenerateReportRequest,
    service: EvidenceReportService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> EvidenceReportResponse:
    try:
        report = await service.generate(
            test_run_id=test_run_id,
            context=context,
            recommendation=payload.recommendation,
            recommendation_reasoning=payload.recommendation_reasoning,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="test run not found"
        ) from exc
    return _to_response(report)


@router.get(
    "/api/v1/reports/{test_run_id}",
    response_model=EvidenceReportResponse,
    summary="Fetch the latest persisted evidence report",
)
async def fetch_latest_report(
    test_run_id: UUID,
    service: EvidenceReportService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> EvidenceReportResponse:
    try:
        report = await service.fetch_latest(test_run_id=test_run_id, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(report)
