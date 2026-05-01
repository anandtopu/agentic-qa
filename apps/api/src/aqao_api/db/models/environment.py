"""WorkspaceEnvironment — Story 1.1.3.

Concrete environment configuration (dev / staging / prod) per workspace.
The freeform string list on ``Workspace.environments`` (Story 1.1.1)
remains as a quick summary; the ground truth is here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class WorkspaceEnvironment(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "workspace_environments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_workspace_environments_workspace_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_production: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
