"""Repository API schemas (Story 1.1.2)."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_FULL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RepositoryLinkRequest(BaseModel):
    installation_id: int = Field(gt=0, description="GitHub App installation id")
    full_name: str = Field(min_length=3, max_length=400, description="owner/name")

    @field_validator("full_name")
    @classmethod
    def _check_full_name(cls, value: str) -> str:
        if not _FULL_NAME_PATTERN.match(value):
            raise ValueError("full_name must be 'owner/name'")
        return value


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    github_installation_id: int
    github_repo_id: int | None
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool
    html_url: str | None
    linked_by: UUID | None
    linked_at: datetime
    unlinked_at: datetime | None
