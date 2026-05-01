"""PolicyService — Story 1.1.3.

Versioned policy log per workspace. Each save creates a new row;
``activate`` flips the ``active`` flag (a single partial unique index
keeps "exactly one active version per workspace" honest).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aqao_api.auth.context import RequestContext
from aqao_api.db.models import Workspace, WorkspacePolicy
from aqao_api.policies.loader import load_policy_yaml
from aqao_api.services.audit import AuditService
from aqao_api.services.errors import ResourceNotFoundError


class PolicyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def get_active(self, workspace_id: UUID) -> WorkspacePolicy:
        stmt = select(WorkspacePolicy).where(
            WorkspacePolicy.workspace_id == workspace_id,
            WorkspacePolicy.active.is_(True),
        )
        policy = self._session.scalars(stmt).first()
        if policy is None:
            raise ResourceNotFoundError("policy", workspace_id)
        return policy

    def list_versions(self, workspace_id: UUID) -> list[WorkspacePolicy]:
        stmt = (
            select(WorkspacePolicy)
            .where(WorkspacePolicy.workspace_id == workspace_id)
            .order_by(WorkspacePolicy.version.desc())
        )
        return list(self._session.scalars(stmt).all())

    # --- mutations --------------------------------------------------------------

    def set(
        self,
        *,
        workspace_id: UUID,
        source_yaml: str,
        context: RequestContext,
        activate: bool = True,
    ) -> WorkspacePolicy:
        """Validate the YAML, persist as a new version, optionally activate.

        Raises :class:`PolicyValidationError` / :class:`PolicyParseError`
        on bad input — the router translates those to 422.
        """
        workspace = self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("workspace", workspace_id)

        policy_model = load_policy_yaml(source_yaml)
        next_version = self._next_version(workspace_id)

        if activate:
            self._session.execute(
                update(WorkspacePolicy)
                .where(
                    WorkspacePolicy.workspace_id == workspace_id,
                    WorkspacePolicy.active.is_(True),
                )
                .values(active=False)
            )
            self._session.flush()

        row = WorkspacePolicy(
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            version=next_version,
            source_yaml=source_yaml,
            parsed=policy_model.model_dump(mode="json"),
            active=activate,
            created_by=context.user_id,
        )
        self._session.add(row)
        self._session.flush()

        self._audit.record(
            context=context,
            action="policy.set",
            resource_type="policy",
            resource_id=row.id,
            payload={
                "workspace_id": str(workspace_id),
                "version": next_version,
                "activated": activate,
            },
        )
        return row

    def activate(
        self,
        *,
        workspace_id: UUID,
        version: int,
        context: RequestContext,
    ) -> WorkspacePolicy:
        target = self._session.scalars(
            select(WorkspacePolicy).where(
                WorkspacePolicy.workspace_id == workspace_id,
                WorkspacePolicy.version == version,
            )
        ).first()
        if target is None:
            raise ResourceNotFoundError("policy_version", (workspace_id, version))

        if not target.active:
            self._session.execute(
                update(WorkspacePolicy)
                .where(
                    WorkspacePolicy.workspace_id == workspace_id,
                    WorkspacePolicy.active.is_(True),
                )
                .values(active=False)
            )
            self._session.flush()
            target.active = True
            self._session.flush()

        self._audit.record(
            context=context,
            action="policy.activate",
            resource_type="policy",
            resource_id=target.id,
            payload={"workspace_id": str(workspace_id), "version": version},
        )
        return target

    # --- helpers ----------------------------------------------------------------

    def _next_version(self, workspace_id: UUID) -> int:
        latest = self._session.scalars(
            select(WorkspacePolicy.version)
            .where(WorkspacePolicy.workspace_id == workspace_id)
            .order_by(WorkspacePolicy.version.desc())
            .limit(1)
        ).first()
        return (latest or 0) + 1
