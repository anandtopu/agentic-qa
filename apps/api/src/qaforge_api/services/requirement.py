"""RequirementService — Story 1.2.

Single ingest entry point that dispatches to the per-type parser,
persists either a ``parsed`` row (success) or a ``failed`` row with
``parse_error`` (failure), and audits.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import (
    Requirement,
    RequirementStatus,
    RequirementType,
    Workspace,
)
from qaforge_api.requirements import ParseError, parse_for
from qaforge_api.services.audit import AuditService
from qaforge_api.services.errors import ResourceNotFoundError


class RequirementService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    # --- queries ----------------------------------------------------------------

    def get(self, requirement_id: UUID) -> Requirement:
        req = self._session.get(Requirement, requirement_id)
        if req is None:
            raise ResourceNotFoundError("requirement", requirement_id)
        return req

    def list(
        self,
        *,
        workspace_id: UUID,
        type: RequirementType | None = None,  # noqa: A002 - mirrors API param
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Requirement]:
        stmt = (
            select(Requirement)
            .where(Requirement.workspace_id == workspace_id)
            .order_by(Requirement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if type is not None:
            stmt = stmt.where(Requirement.type == type)
        return list(self._session.scalars(stmt).all())

    # --- mutations --------------------------------------------------------------

    def ingest(
        self,
        *,
        workspace_id: UUID,
        type: RequirementType,  # noqa: A002 - mirrors API field name
        raw: dict[str, Any],
        context: RequestContext,
        source_ref: str | None = None,
    ) -> Requirement:
        """Parse ``raw`` per ``type`` and persist the requirement.

        On parse failure the row is still persisted with status
        ``failed`` and ``parse_error`` set — this preserves the input
        for triage rather than throwing it away.
        """
        workspace = self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("workspace", workspace_id)

        try:
            parsed = parse_for(type, raw)
            row = Requirement(
                tenant_id=context.tenant_id,
                workspace_id=workspace_id,
                type=type,
                status=RequirementStatus.PARSED,
                source_ref=source_ref or parsed.source_ref,
                commit_sha=parsed.commit_sha,
                raw_payload=raw,
                parsed={"summary": parsed.summary, **parsed.payload},
                parse_error=None,
                ingested_by=context.user_id,
            )
        except ParseError as exc:
            row = Requirement(
                tenant_id=context.tenant_id,
                workspace_id=workspace_id,
                type=type,
                status=RequirementStatus.FAILED,
                source_ref=source_ref,
                commit_sha=None,
                raw_payload=raw,
                parsed={},
                parse_error=str(exc),
                ingested_by=context.user_id,
            )

        self._session.add(row)
        self._session.flush()

        self._audit.record(
            context=context,
            action=(
                "requirement.ingested"
                if row.status is RequirementStatus.PARSED
                else "requirement.parse_failed"
            ),
            resource_type="requirement",
            resource_id=row.id,
            payload={
                "workspace_id": str(workspace_id),
                "type": type.value,
                "source_ref": row.source_ref,
                "commit_sha": row.commit_sha,
            },
        )
        return row
