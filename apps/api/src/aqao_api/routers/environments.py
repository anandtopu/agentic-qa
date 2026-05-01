"""Environment routes — Story 1.1.3."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.schemas.environment import (
    EnvironmentListResponse,
    EnvironmentResponse,
    EnvironmentUpsertRequest,
)
from aqao_api.services.environment import EnvironmentService
from aqao_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/environments",
    tags=["workspaces"],
)


def _service(session: Session = Depends(tenant_scoped_session)) -> EnvironmentService:
    return EnvironmentService(session)


@router.get(
    "",
    response_model=EnvironmentListResponse,
    summary="List environments configured on a workspace",
)
def list_environments(
    workspace_id: UUID,
    service: EnvironmentService = Depends(_service),
) -> EnvironmentListResponse:
    envs = service.list(workspace_id)
    return EnvironmentListResponse(
        environments=[EnvironmentResponse.model_validate(e) for e in envs]
    )


@router.put(
    "/{name}",
    response_model=EnvironmentResponse,
    summary="Create or update an environment by name",
)
def upsert_environment(
    workspace_id: UUID,
    name: str,
    payload: EnvironmentUpsertRequest,
    service: EnvironmentService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> EnvironmentResponse:
    if payload.name != name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="path name and body name must match",
        )
    try:
        env = service.upsert(
            workspace_id=workspace_id,
            name=payload.name,
            base_url=payload.base_url,
            is_production=payload.is_production,
            variables=payload.variables,
            description=payload.description,
            context=context,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        ) from exc
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return EnvironmentResponse.model_validate(env)


@router.get(
    "/{name}",
    response_model=EnvironmentResponse,
    summary="Get a workspace environment by name",
)
def get_environment(
    workspace_id: UUID,
    name: str,
    service: EnvironmentService = Depends(_service),
) -> EnvironmentResponse:
    try:
        env = service.get(workspace_id, name)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="environment not found"
        ) from exc
    return EnvironmentResponse.model_validate(env)


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace environment",
)
def delete_environment(
    workspace_id: UUID,
    name: str,
    service: EnvironmentService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> None:
    try:
        service.delete(workspace_id=workspace_id, name=name, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="environment not found"
        ) from exc
