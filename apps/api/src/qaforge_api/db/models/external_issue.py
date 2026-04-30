"""ExternalIssue ORM — Stories 3.2.1 / 3.2.2.

Links a QAForge defect to an issue in an external tracker (Jira,
GitHub). Powers dedup ("did we already file?") and close-sync (the
upstream tracker's webhook updates ``status`` here within seconds).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from qaforge_api.db.base import Base
from qaforge_api.db.models.mixins import (
    CreatedAtMixin,
    TenantScopedMixin,
    UUIDPrimaryKeyMixin,
)


class IssueProvider(StrEnum):
    JIRA = "jira"
    GITHUB = "github"


class IssueStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


_TERMINAL = frozenset({IssueStatus.RESOLVED, IssueStatus.CLOSED, IssueStatus.REJECTED})


def is_terminal_status(status: IssueStatus) -> bool:
    return status in _TERMINAL


class ExternalIssue(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "external_issues"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider",
            "issue_key",
            name="uq_external_issues_workspace_provider_issue",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    classification_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("failure_classifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    signal_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    project_key: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(200), nullable=False)
    issue_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="open")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    opened_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
