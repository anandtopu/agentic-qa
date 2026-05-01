"""Repository — Story 1.1.2.

Models a GitHub repository linked to a workspace via a GitHub App
installation. ``unlinked_at`` is set by ``RepositoryService.unlink``;
the row is kept (not deleted) so the audit trail and historical test
runs keep their FK targets intact.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import (
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Repository(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "repositories"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    github_installation_id: Mapped[int] = mapped_column(nullable=False)
    github_repo_id: Mapped[int | None] = mapped_column(nullable=True)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[str] = mapped_column(String(400), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, server_default="main")
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    html_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linked_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    unlinked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    @property
    def is_linked(self) -> bool:
        return self.unlinked_at is None
