"""AuditQueryService — Story 2.4.2.

Read-side service for the audit timeline + export. Verification status
is computed per row so the API client (and the UI) can flag tampered
rows immediately.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqao_api.audit.signing import (
    AuditSignatureStatus,
    canonical_payload,
    verify_signature,
)
from aqao_api.db.models import AuditEvent


@dataclass(slots=True)
class VerifiedAuditEvent:
    event: AuditEvent
    status: AuditSignatureStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.event.id),
            "tenant_id": str(self.event.tenant_id),
            "actor_user_id": (str(self.event.actor_user_id) if self.event.actor_user_id else None),
            "action": self.event.action,
            "resource_type": self.event.resource_type,
            "resource_id": self.event.resource_id,
            "payload": dict(self.event.payload or {}),
            "correlation_id": self.event.correlation_id,
            "signature": self.event.signature,
            "signature_status": self.status.value,
            "created_at": self.event.created_at.isoformat(),
        }


class AuditQueryService:
    def __init__(self, session: Session, *, hmac_key: str) -> None:
        self._session = session
        self._hmac_key = hmac_key

    def query(
        self,
        *,
        actor_user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[VerifiedAuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
        if actor_user_id is not None:
            stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
        if resource_type is not None:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        if resource_id is not None:
            stmt = stmt.where(AuditEvent.resource_id == resource_id)
        if action is not None:
            stmt = stmt.where(AuditEvent.action == action)
        if since is not None:
            stmt = stmt.where(AuditEvent.created_at >= since)
        if until is not None:
            stmt = stmt.where(AuditEvent.created_at < until)

        rows = list(self._session.scalars(stmt).all())
        return [self._verify(row) for row in rows]

    def export_csv(self, events: Sequence[VerifiedAuditEvent]) -> str:
        buffer = StringIO()
        fieldnames = [
            "id",
            "created_at",
            "tenant_id",
            "actor_user_id",
            "action",
            "resource_type",
            "resource_id",
            "correlation_id",
            "signature_status",
            "payload",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for ve in events:
            row = ve.to_dict()
            row["payload"] = json.dumps(row["payload"], sort_keys=True)
            writer.writerow({k: row.get(k, "") for k in fieldnames})
        return buffer.getvalue()

    def export_json(self, events: Sequence[VerifiedAuditEvent]) -> str:
        return json.dumps([ve.to_dict() for ve in events], default=str, indent=2)

    def stream_json_lines(self, events: Sequence[VerifiedAuditEvent]) -> Iterator[str]:
        for ve in events:
            yield json.dumps(ve.to_dict(), default=str)

    # --- internals --------------------------------------------------------------

    def _verify(self, event: AuditEvent) -> VerifiedAuditEvent:
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
        status = verify_signature(self._hmac_key, body=body, stored_signature=event.signature)
        return VerifiedAuditEvent(event=event, status=status)
