"""AuditService — append-only writes to ``audit_events``.

PRD §14.4 + Story 1.1.1 require every workspace state change to be
auditable. Phase 2 Story 2.4.1 layered on HMAC-SHA256 signing — every
new row gets a ``signature`` so a verifier sweep can spot tampering.

The signing key is read from settings on the first ``record()`` call
and cached on the service instance so a long-lived API process
doesn't re-fetch the secret per write.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from qaforge_api.audit.signing import canonical_payload, compute_signature
from qaforge_api.auth.context import RequestContext
from qaforge_api.config import get_settings
from qaforge_api.db.models import AuditEvent


class AuditService:
    """Single insert point for the audit trail."""

    def __init__(self, session: Session, *, hmac_key: str | None = None) -> None:
        self._session = session
        self._hmac_key = hmac_key
        self._log = structlog.get_logger("qaforge_api.services.audit")

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

        signature = self._sign(event)
        if signature is not None:
            event.signature = signature
            self._session.flush()
        return event

    def _sign(self, event: AuditEvent) -> str | None:
        secret = self._resolve_key()
        if not secret:
            self._log.warning(
                "audit.signing_skipped",
                reason="QAFORGE_AUDIT_HMAC_KEY missing or empty",
                event_id=str(event.id),
            )
            return None
        body = canonical_payload(
            audit_id=event.id,
            tenant_id=event.tenant_id,
            actor_user_id=event.actor_user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            payload=dict(event.payload or {}),
            correlation_id=event.correlation_id,
            created_at=event.created_at,
        )
        return compute_signature(secret, body=body)

    def _resolve_key(self) -> str:
        if self._hmac_key is not None:
            return self._hmac_key
        secret = get_settings().audit_hmac_key
        return secret.get_secret_value() if secret is not None else ""
