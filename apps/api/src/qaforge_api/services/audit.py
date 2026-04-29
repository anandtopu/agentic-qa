"""AuditService — append-only writes to ``audit_events``.

PRD §14.4 + Story 1.1.1 require every workspace state change to be
auditable. Phase 2 Story 2.4.1 will additionally HMAC-sign each row;
this service is the single insert point so signing plugs in here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from qaforge_api.auth.context import RequestContext
from qaforge_api.db.models import AuditEvent


class AuditService:
    """Single insert point for the audit trail."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        context: RequestContext,
        action: str,
        resource_type: str,
        resource_id: UUID | str | None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            payload=payload or {},
            correlation_id=context.correlation_id,
        )
        self._session.add(event)
        self._session.flush()  # populate id + created_at without committing
        return event
