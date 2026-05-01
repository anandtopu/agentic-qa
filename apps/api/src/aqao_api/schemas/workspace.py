"""Workspace API schemas (PRD §9.1)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aqao_api.db.models.workspace import ApplicationType


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    application_type: ApplicationType
    repo_url: str | None = Field(default=None, max_length=500)
    default_branch: str = Field(default="main", min_length=1, max_length=100)
    environments: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("environments")
    @classmethod
    def _normalise_envs(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if v and v.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("environments must be unique")
        return cleaned


class WorkspaceUpdateRequest(BaseModel):
    """All fields optional. Sending ``null`` for a nullable field clears it.

    Fields you don't want to touch should simply be omitted.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    application_type: ApplicationType | None = None
    repo_url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, min_length=1, max_length=100)
    environments: list[str] | None = None
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("environments")
    @classmethod
    def _normalise_envs(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [v.strip() for v in value if v and v.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("environments must be unique")
        return cleaned


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    repo_url: str | None
    default_branch: str
    application_type: ApplicationType
    environments: list[str]
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceResponse]
    limit: int
    offset: int
