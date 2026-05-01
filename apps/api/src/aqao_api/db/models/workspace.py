"""Workspace — Story 1.1.1.

Carries the PRD §9.1 fields plus tenant_id for RLS. Repository linkage
beyond ``repo_url`` (GitHub App install) lands in Story 1.1.2; richer
per-environment configuration in Story 1.1.3.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ApplicationType(StrEnum):
    WEB_API = "web_api"
    WEB_UI = "web_ui"
    WEB_FULL_STACK = "web_full_stack"
    MOBILE_APP = "mobile_app"
    BACKEND_SERVICE = "backend_service"
    LIBRARY = "library"
    OTHER = "other"


class Workspace(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_workspaces_tenant_id_name"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, server_default="main")
    application_type: Mapped[ApplicationType] = mapped_column(
        SAEnum(ApplicationType, name="application_type", native_enum=False, length=32),
        nullable=False,
    )
    environments: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "repo_url": self.repo_url,
            "default_branch": self.default_branch,
            "application_type": self.application_type,
            "environments": list(self.environments),
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
        }
