"""Approval API schemas — Story 2.1.3.

Wire types for ``/api/v1/approvals``. The router is the only mutating
surface; agent-side step authors should reach for the in-process
``ApprovalService`` directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecisionRequest(BaseModel):
    """Body for POST /approve and POST /reject."""

    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(default=None, max_length=2_000)


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    tenant_id: UUID
    workspace_id: UUID | None
    test_run_id: UUID | None
    event_type: str
    state: str
    subject: str
    reason: str | None
    context: dict[str, Any]
    requested_by: UUID | None
    decided_by: UUID | None
    decision_comment: str | None
    expires_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ApprovalRequestResponse]
