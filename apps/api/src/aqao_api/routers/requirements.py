"""Manual requirement ingest routes — Story 1.2 (manual upload path)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.models.requirement import RequirementType
from aqao_api.db.session import tenant_scoped_session
from aqao_api.schemas.requirement import (
    RequirementIngestRequest,
    RequirementListResponse,
    RequirementResponse,
)
from aqao_api.services.errors import ResourceNotFoundError
from aqao_api.services.requirement import RequirementService

per_workspace = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/requirements",
    tags=["requirements"],
)
flat = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])


def _service(session: Session = Depends(tenant_scoped_session)) -> RequirementService:
    return RequirementService(session)


@per_workspace.post(
    "",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a requirement (story, AC, OpenAPI, Postman, SQL schema, PR diff)",
)
def ingest_requirement(
    workspace_id: UUID,
    payload: RequirementIngestRequest,
    service: RequirementService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> RequirementResponse:
    try:
        row = service.ingest(
            workspace_id=workspace_id,
            type=payload.type,
            raw=payload.payload,
            context=context,
            source_ref=payload.source_ref,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        ) from exc
    return RequirementResponse.model_validate(row)


@per_workspace.get(
    "",
    response_model=RequirementListResponse,
    summary="List ingested requirements for a workspace",
)
def list_requirements(
    workspace_id: UUID,
    type: RequirementType | None = Query(default=None),  # noqa: A002 - query param name
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: RequirementService = Depends(_service),
) -> RequirementListResponse:
    rows = service.list(workspace_id=workspace_id, type=type, limit=limit, offset=offset)
    return RequirementListResponse(
        requirements=[RequirementResponse.model_validate(r) for r in rows],
        limit=limit,
        offset=offset,
    )


@flat.get(
    "/{requirement_id}",
    response_model=RequirementResponse,
    summary="Get a requirement by id",
)
def get_requirement(
    requirement_id: UUID,
    service: RequirementService = Depends(_service),
) -> RequirementResponse:
    try:
        row = service.get(requirement_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="requirement not found",
        ) from exc
    return RequirementResponse.model_validate(row)
