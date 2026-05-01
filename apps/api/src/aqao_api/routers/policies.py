"""Policy routes — Story 1.1.3.

422 responses include field-level errors from the policy validator so a
UI editor can highlight the offending lines.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.policies.errors import PolicyParseError, PolicyValidationError
from aqao_api.schemas.policy import (
    PolicyHistoryResponse,
    PolicySetRequest,
    PolicyVersionResponse,
)
from aqao_api.services.errors import ResourceNotFoundError
from aqao_api.services.policy import PolicyService

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/policy",
    tags=["workspaces"],
)


def _service(session: Session = Depends(tenant_scoped_session)) -> PolicyService:
    return PolicyService(session)


@router.put(
    "",
    response_model=PolicyVersionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a new policy version (validates PRD §10.3 schema)",
)
def set_policy(
    workspace_id: UUID,
    payload: PolicySetRequest,
    service: PolicyService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> JSONResponse | PolicyVersionResponse:
    try:
        row = service.set(
            workspace_id=workspace_id,
            source_yaml=payload.source_yaml,
            context=context,
            activate=payload.activate,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found"
        ) from exc
    except PolicyParseError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "policy YAML failed to parse",
                "errors": [
                    {
                        "loc": [],
                        "msg": str(exc),
                        "type": "yaml_parse_error",
                        "line": exc.line,
                        "column": exc.column,
                    }
                ],
            },
        )
    except PolicyValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "policy validation failed",
                "errors": [e.to_dict() for e in exc.errors],
            },
        )

    return PolicyVersionResponse.model_validate(row)


@router.get(
    "",
    response_model=PolicyVersionResponse,
    summary="Get the active policy version for a workspace",
)
def get_active_policy(
    workspace_id: UUID,
    service: PolicyService = Depends(_service),
) -> PolicyVersionResponse:
    try:
        row = service.get_active(workspace_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active policy",
        ) from exc
    return PolicyVersionResponse.model_validate(row)


@router.get(
    "/history",
    response_model=PolicyHistoryResponse,
    summary="List historical policy versions (newest first)",
)
def list_policy_history(
    workspace_id: UUID,
    service: PolicyService = Depends(_service),
) -> PolicyHistoryResponse:
    versions = service.list_versions(workspace_id)
    return PolicyHistoryResponse(
        versions=[PolicyVersionResponse.model_validate(v) for v in versions]
    )


@router.post(
    "/activate/{version}",
    response_model=PolicyVersionResponse,
    summary="Activate a previous policy version",
)
def activate_policy_version(
    workspace_id: UUID,
    version: int,
    service: PolicyService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> PolicyVersionResponse:
    try:
        row = service.activate(workspace_id=workspace_id, version=version, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="policy version not found",
        ) from exc
    return PolicyVersionResponse.model_validate(row)
