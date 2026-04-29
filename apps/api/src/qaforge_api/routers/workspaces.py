"""Workspace API routes — Story 1.1.1.

The router is a thin shell that translates HTTP into service calls and
service errors into HTTP status codes. Tenant scoping (RLS) is provided
by the ``tenant_scoped_session`` dependency.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext, require_request_context
from qaforge_api.db.session import tenant_scoped_session
from qaforge_api.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from qaforge_api.services.errors import DuplicateResourceError, ResourceNotFoundError
from qaforge_api.services.workspace import (
    WorkspaceCreate,
    WorkspaceService,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


def _service(session: Session = Depends(tenant_scoped_session)) -> WorkspaceService:
    return WorkspaceService(session)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
def create_workspace(
    payload: WorkspaceCreateRequest,
    service: WorkspaceService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> WorkspaceResponse:
    try:
        workspace = service.create(
            WorkspaceCreate(
                name=payload.name,
                application_type=payload.application_type,
                repo_url=payload.repo_url,
                default_branch=payload.default_branch,
                environments=payload.environments,
                description=payload.description,
            ),
            context=context,
        )
    except DuplicateResourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return WorkspaceResponse.model_validate(workspace)


@router.get(
    "",
    response_model=WorkspaceListResponse,
    summary="List workspaces in the caller's tenant",
)
def list_workspaces(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = Query(default=False),
    service: WorkspaceService = Depends(_service),
) -> WorkspaceListResponse:
    workspaces = service.list(
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return WorkspaceListResponse(
        workspaces=[WorkspaceResponse.model_validate(w) for w in workspaces],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get a workspace by id",
)
def get_workspace(
    workspace_id: UUID,
    service: WorkspaceService = Depends(_service),
) -> WorkspaceResponse:
    try:
        workspace = service.get(workspace_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        ) from exc
    return WorkspaceResponse.model_validate(workspace)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update a workspace",
)
def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdateRequest,
    service: WorkspaceService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> WorkspaceResponse:
    update_payload = _build_update(payload)
    try:
        workspace = service.update(workspace_id, update_payload, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        ) from exc
    except DuplicateResourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return WorkspaceResponse.model_validate(workspace)


def _build_update(payload: WorkspaceUpdateRequest) -> WorkspaceUpdate:
    """Translate the API patch payload to the service-layer DTO.

    Pydantic ``model_dump(exclude_unset=True)`` distinguishes "field
    omitted" (don't touch) from "field set to null" (clear it).
    """
    provided = payload.model_dump(exclude_unset=True)
    kwargs: dict[str, object] = {}
    if "name" in provided:
        kwargs["name"] = provided["name"]
    if "application_type" in provided:
        kwargs["application_type"] = provided["application_type"]
    if "repo_url" in provided:
        kwargs["repo_url"] = provided["repo_url"]
    if "default_branch" in provided:
        kwargs["default_branch"] = provided["default_branch"]
    if "environments" in provided:
        kwargs["environments"] = provided["environments"]
    if "description" in provided:
        kwargs["description"] = provided["description"]
    return WorkspaceUpdate(**kwargs)  # type: ignore[arg-type]
