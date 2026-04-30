"""Audit query API schemas — Story 2.4.2."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    payload: dict[str, Any]
    correlation_id: str | None
    signature: str | None
    signature_status: str
    created_at: datetime


class AuditQueryResponse(BaseModel):
    events: list[AuditEventResponse]
    limit: int
    offset: int
