"""Repository link/unlink routes — Story 1.1.2."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext, require_request_context
from aqao_api.db.session import tenant_scoped_session
from aqao_api.integrations.github.client import GitHubClient, get_github_client
from aqao_api.schemas.repository import RepositoryLinkRequest, RepositoryResponse
from aqao_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)
from aqao_api.services.repository import (
    RepositoryLinkFailed,
    RepositoryService,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/repository",
    tags=["repositories"],
)


def _service(
    session: Session = Depends(tenant_scoped_session),
    github: GitHubClient = Depends(get_github_client),
) -> RepositoryService:
    return RepositoryService(session, github)


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a GitHub repository to a workspace",
)
async def link_repository(
    workspace_id: UUID,
    payload: RepositoryLinkRequest,
    service: RepositoryService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> RepositoryResponse:
    try:
        repository = await service.link(
            workspace_id=workspace_id,
            installation_id=payload.installation_id,
            full_name=payload.full_name,
            context=context,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        ) from exc
    except DuplicateResourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="workspace already has an active repository linkage",
        ) from exc
    except RepositoryLinkFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"github metadata fetch failed: {exc}",
        ) from exc
    return RepositoryResponse.model_validate(repository)


@router.get(
    "",
    response_model=RepositoryResponse,
    summary="Get the active repository linkage",
)
def get_repository(
    workspace_id: UUID,
    service: RepositoryService = Depends(_service),
) -> RepositoryResponse:
    try:
        repository = service.get_active_or_404(workspace_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active repository linkage",
        ) from exc
    return RepositoryResponse.model_validate(repository)


@router.delete(
    "",
    response_model=RepositoryResponse,
    summary="Unlink the active repository (best-effort GitHub revoke)",
)
async def unlink_repository(
    workspace_id: UUID,
    service: RepositoryService = Depends(_service),
    context: RequestContext = Depends(require_request_context),
) -> RepositoryResponse:
    try:
        repository = await service.unlink(workspace_id=workspace_id, context=context)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active repository linkage",
        ) from exc
    return RepositoryResponse.model_validate(repository)
