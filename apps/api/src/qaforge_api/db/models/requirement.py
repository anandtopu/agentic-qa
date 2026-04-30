"""Requirement — Story 1.2.

Captures every input that drives downstream agents: PR diffs, user
stories with acceptance criteria, OpenAPI / Postman / SQL schemas. Each
row carries both the raw input (preserved verbatim for audit) and the
normalised parsed form.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class RequirementType(StrEnum):
    PR_DIFF = "pr_diff"
    USER_STORY = "user_story"
    OPENAPI = "openapi"
    POSTMAN = "postman"
    SQL_SCHEMA = "sql_schema"


class RequirementStatus(StrEnum):
    PARSED = "parsed"
    FAILED = "failed"


class Requirement(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "requirements"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[RequirementType] = mapped_column(
        SAEnum(RequirementType, name="requirement_type", native_enum=False, length=32),
        nullable=False,
    )
    status: Mapped[RequirementStatus] = mapped_column(
        SAEnum(
            RequirementStatus,
            name="requirement_status",
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
