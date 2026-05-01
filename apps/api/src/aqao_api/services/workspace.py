"""WorkspaceService — create / read / list / update for Workspace.

Story 1.1.1. RLS (ADR-0007) is enforced by the session that backs this
service — the service never filters by ``tenant_id`` itself; that's the
DB's job. Reaching another tenant's row is structurally impossible.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import Workspace
from aqao_api.db.models.workspace import ApplicationType
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)


class WorkspaceCreate:
    """Plain DTO so the service doesn't import API schemas."""

    __slots__ = (
        "application_type",
        "default_branch",
        "description",
        "environments",
        "name",
        "repo_url",
    )

    def __init__(
        self,
        *,
        name: str,
        application_type: ApplicationType,
        repo_url: str | None = None,
        default_branch: str = "main",
        environments: Sequence[str] = (),
        description: str | None = None,
    ) -> None:
        self.name = name
        self.application_type = application_type
        self.repo_url = repo_url
        self.default_branch = default_branch
        self.environments = list(environments)
        self.description = description


class WorkspaceUpdate:
    __slots__ = (
        "application_type",
        "default_branch",
        "description",
        "environments",
        "name",
        "repo_url",
    )

    def __init__(
        self,
        *,
        name: str | None = None,
        application_type: ApplicationType | None = None,
        repo_url: str | None | _Sentinel = ...,  # type: ignore[assignment]
        default_branch: str | None = None,
        environments: Sequence[str] | None = None,
        description: str | None | _Sentinel = ...,  # type: ignore[assignment]
    ) -> None:
        self.name = name
        self.application_type = application_type
        self.repo_url = repo_url
        self.default_branch = default_branch
        self.environments = None if environments is None else list(environments)
        self.description = description


class _Sentinel:
    pass


_UNSET = _Sentinel()


class WorkspaceService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def get(self, workspace_id: UUID) -> Workspace:
        workspace = self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("workspace", workspace_id)
        return workspace

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Workspace]:
        stmt = select(Workspace).order_by(Workspace.created_at.desc()).limit(limit).offset(offset)
        if not include_archived:
            stmt = stmt.where(Workspace.archived_at.is_(None))
        return list(self._session.scalars(stmt).all())

    # --- mutations --------------------------------------------------------------

    def create(self, payload: WorkspaceCreate, *, context: RequestContext) -> Workspace:
        workspace = Workspace(
            tenant_id=context.tenant_id,
            name=payload.name,
            repo_url=payload.repo_url,
            default_branch=payload.default_branch,
            application_type=payload.application_type,
            environments=list(payload.environments),
            description=payload.description,
            created_by=context.user_id,
        )
        self._session.add(workspace)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if _is_unique_violation(exc, "uq_workspaces_tenant_id_name"):
                raise DuplicateResourceError("workspace", "name", payload.name) from exc
            raise

        self._audit.record(
            context=context,
            action="workspace.create",
            resource_type="workspace",
            resource_id=workspace.id,
            payload={
                "name": workspace.name,
                "application_type": workspace.application_type.value,
                "default_branch": workspace.default_branch,
            },
        )
        return workspace

    def update(
        self,
        workspace_id: UUID,
        payload: WorkspaceUpdate,
        *,
        context: RequestContext,
    ) -> Workspace:
        workspace = self.get(workspace_id)

        changed: dict[str, Any] = {}
        if payload.name is not None and payload.name != workspace.name:
            changed["name"] = {"old": workspace.name, "new": payload.name}
            workspace.name = payload.name
        if (
            payload.application_type is not None
            and payload.application_type != workspace.application_type
        ):
            changed["application_type"] = {
                "old": workspace.application_type.value,
                "new": payload.application_type.value,
            }
            workspace.application_type = payload.application_type
        if not isinstance(payload.repo_url, _Sentinel) and payload.repo_url != workspace.repo_url:
            changed["repo_url"] = {"old": workspace.repo_url, "new": payload.repo_url}
            workspace.repo_url = payload.repo_url
        if (
            payload.default_branch is not None
            and payload.default_branch != workspace.default_branch
        ):
            changed["default_branch"] = {
                "old": workspace.default_branch,
                "new": payload.default_branch,
            }
            workspace.default_branch = payload.default_branch
        if payload.environments is not None and payload.environments != list(
            workspace.environments
        ):
            changed["environments"] = {
                "old": list(workspace.environments),
                "new": payload.environments,
            }
            workspace.environments = list(payload.environments)
        if (
            not isinstance(payload.description, _Sentinel)
            and payload.description != workspace.description
        ):
            changed["description"] = {"old": workspace.description, "new": payload.description}
            workspace.description = payload.description

        if not changed:
            return workspace

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if _is_unique_violation(exc, "uq_workspaces_tenant_id_name"):
                raise DuplicateResourceError(
                    "workspace", "name", changed.get("name", {}).get("new", workspace.name)
                ) from exc
            raise

        self._audit.record(
            context=context,
            action="workspace.update",
            resource_type="workspace",
            resource_id=workspace.id,
            payload={"changes": changed},
        )
        return workspace

    def archive(self, workspace_id: UUID, *, context: RequestContext) -> Workspace:
        workspace = self.get(workspace_id)
        if workspace.archived_at is not None:
            return workspace
        workspace.archived_at = datetime.now(UTC)
        self._session.flush()
        self._audit.record(
            context=context,
            action="workspace.archive",
            resource_type="workspace",
            resource_id=workspace.id,
        )
        return workspace


def _is_unique_violation(exc: IntegrityError, constraint: str) -> bool:
    """Best-effort check across psycopg + SQLAlchemy error shapes."""
    text = str(exc.orig) if exc.orig is not None else str(exc)
    return constraint in text or "duplicate key" in text.lower()
