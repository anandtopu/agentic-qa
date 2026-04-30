"""EnvironmentService — Story 1.1.3."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import Workspace, WorkspaceEnvironment
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
)


class EnvironmentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    def list(self, workspace_id: UUID) -> list[WorkspaceEnvironment]:
        stmt = (
            select(WorkspaceEnvironment)
            .where(WorkspaceEnvironment.workspace_id == workspace_id)
            .order_by(WorkspaceEnvironment.name.asc())
        )
        return list(self._session.scalars(stmt).all())

    def get(self, workspace_id: UUID, name: str) -> WorkspaceEnvironment:
        stmt = select(WorkspaceEnvironment).where(
            WorkspaceEnvironment.workspace_id == workspace_id,
            WorkspaceEnvironment.name == name,
        )
        env = self._session.scalars(stmt).first()
        if env is None:
            raise ResourceNotFoundError("environment", (workspace_id, name))
        return env

    def upsert(
        self,
        *,
        workspace_id: UUID,
        name: str,
        base_url: str | None = None,
        is_production: bool = False,
        variables: Mapping[str, Any] | None = None,
        description: str | None = None,
        context: RequestContext,
    ) -> WorkspaceEnvironment:
        workspace = self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("workspace", workspace_id)

        existing = self._session.scalars(
            select(WorkspaceEnvironment).where(
                WorkspaceEnvironment.workspace_id == workspace_id,
                WorkspaceEnvironment.name == name,
            )
        ).first()

        if existing is None:
            env = WorkspaceEnvironment(
                tenant_id=context.tenant_id,
                workspace_id=workspace_id,
                name=name,
                base_url=base_url,
                is_production=is_production,
                variables=dict(variables or {}),
                description=description,
            )
            self._session.add(env)
            try:
                self._session.flush()
            except IntegrityError as exc:
                self._session.rollback()
                raise DuplicateResourceError("environment", "name", name) from exc

            self._audit.record(
                context=context,
                action="environment.create",
                resource_type="environment",
                resource_id=env.id,
                payload={"workspace_id": str(workspace_id), "name": name},
            )
            return env

        existing.base_url = base_url
        existing.is_production = is_production
        existing.variables = dict(variables or {})
        existing.description = description
        self._session.flush()
        self._audit.record(
            context=context,
            action="environment.update",
            resource_type="environment",
            resource_id=existing.id,
            payload={"workspace_id": str(workspace_id), "name": name},
        )
        return existing

    def delete(self, *, workspace_id: UUID, name: str, context: RequestContext) -> None:
        env = self.get(workspace_id, name)
        self._session.execute(delete(WorkspaceEnvironment).where(WorkspaceEnvironment.id == env.id))
        self._audit.record(
            context=context,
            action="environment.delete",
            resource_type="environment",
            resource_id=env.id,
            payload={"workspace_id": str(workspace_id), "name": name},
        )
