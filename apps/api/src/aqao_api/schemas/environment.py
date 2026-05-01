"""Environment API schemas — Story 1.1.3."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    base_url: str | None = Field(default=None, max_length=500)
    is_production: bool = False
    variables: dict[str, Any] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=500)


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    base_url: str | None
    is_production: bool
    variables: dict[str, Any]
    description: str | None
    created_at: datetime
    updated_at: datetime


class EnvironmentListResponse(BaseModel):
    environments: list[EnvironmentResponse]
