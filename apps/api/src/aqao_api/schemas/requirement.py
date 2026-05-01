"""Requirement API schemas — Story 1.2."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aqao_api.db.models.requirement import RequirementStatus, RequirementType


class RequirementIngestRequest(BaseModel):
    type: RequirementType
    source_ref: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(
        ...,
        description="Type-specific raw input. See PRD §9.2 for shapes.",
    )


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    type: RequirementType
    status: RequirementStatus
    source_ref: str | None
    commit_sha: str | None
    parsed: dict[str, Any]
    parse_error: str | None
    ingested_by: UUID | None
    created_at: datetime
    updated_at: datetime


class RequirementListResponse(BaseModel):
    requirements: list[RequirementResponse]
    limit: int
    offset: int
