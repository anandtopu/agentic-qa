"""Policy API schemas — Story 1.1.3."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicySetRequest(BaseModel):
    """Caller submits raw YAML; the server validates against PRD §10.3."""

    source_yaml: str = Field(min_length=1, max_length=64_000)
    activate: bool = True


class PolicyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    version: int
    active: bool
    parsed: dict[str, Any]
    source_yaml: str
    created_by: UUID | None
    created_at: datetime


class PolicyHistoryResponse(BaseModel):
    versions: list[PolicyVersionResponse]


class PolicyValidationErrorBody(BaseModel):
    """422 body shape when the YAML fails the schema."""

    detail: str = "policy validation failed"
    errors: list[dict[str, Any]]
