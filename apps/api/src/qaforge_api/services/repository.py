"""RepositoryService — Story 1.1.2.

Owns the GitHub-app linkage workflow: link a repo to a workspace,
fetch metadata via the GitHub client, audit, and unlink (calling the
GitHub revoke endpoint best-effort).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import Repository, Workspace
from qaforge_api.integrations.github.client import (
    GitHubClient,
    GitHubError,
    RepositoryInfo,
)
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ServiceError,
)


class RepositoryLinkFailed(ServiceError):  # noqa: N818 - public name predates rule
    """Raised when GitHub metadata fetch fails — the link does not persist."""


class RepositoryService:
    def __init__(self, session: Session, github: GitHubClient) -> None:
        self._session = session
        self._github = github
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def get_active(self, workspace_id: UUID) -> Repository | None:
        stmt = (
            select(Repository)
            .where(
                Repository.workspace_id == workspace_id,
                Repository.unlinked_at.is_(None),
            )
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def get_active_or_404(self, workspace_id: UUID) -> Repository:
        repository = self.get_active(workspace_id)
        if repository is None:
            raise ResourceNotFoundError("repository", workspace_id)
        return repository

    # --- mutations --------------------------------------------------------------

    async def link(
        self,
        *,
        workspace_id: UUID,
        installation_id: int,
        full_name: str,
        context: RequestContext,
    ) -> Repository:
        workspace = self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("workspace", workspace_id)

        existing = self.get_active(workspace_id)
        if existing is not None:
            raise DuplicateResourceError("repository", "workspace_id", workspace_id)

        try:
            info: RepositoryInfo = await self._github.get_repository(installation_id, full_name)
        except GitHubError as err:
            raise RepositoryLinkFailed(str(err)) from err

        repository = Repository(
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            github_installation_id=installation_id,
            github_repo_id=info.id,
            owner=info.owner,
            name=info.name,
            full_name=info.full_name,
            default_branch=info.default_branch,
            private=info.private,
            html_url=info.html_url,
            linked_by=context.user_id,
            linked_at=datetime.now(UTC),
        )
        self._session.add(repository)
        self._session.flush()

        # Denormalise the URL on the workspace for quick reads.
        workspace.repo_url = info.html_url
        workspace.default_branch = info.default_branch

        self._audit.record(
            context=context,
            action="repository.link",
            resource_type="repository",
            resource_id=repository.id,
            payload={
                "workspace_id": str(workspace_id),
                "full_name": info.full_name,
                "installation_id": installation_id,
            },
        )
        return repository

    async def unlink(self, *, workspace_id: UUID, context: RequestContext) -> Repository:
        repository = self.get_active_or_404(workspace_id)
        repository.unlinked_at = datetime.now(UTC)
        self._session.flush()

        revoke_succeeded = True
        try:
            await self._github.revoke_installation(repository.github_installation_id)
        except GitHubError:
            revoke_succeeded = False

        self._audit.record(
            context=context,
            action="repository.unlink",
            resource_type="repository",
            resource_id=repository.id,
            payload={
                "workspace_id": str(workspace_id),
                "github_installation_id": repository.github_installation_id,
                "revoke_succeeded": revoke_succeeded,
            },
        )
        return repository
