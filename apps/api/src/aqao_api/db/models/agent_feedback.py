"""AgentFeedback ORM — Story 6.3.1.

Append-only thumbs up/down rating on any agent output, identified
by ``(resource_type, resource_id)``. Negative ratings are the input
to the weekly low-rated review and to the eval-case conversion path.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from aqao_api.db.base import Base
from aqao_api.db.models.mixins import (
    TenantScopedMixin,
    UUIDPrimaryKeyMixin,
)


class FeedbackRating(StrEnum):
    UP = "up"
    DOWN = "down"


class AgentFeedback(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    __tablename__ = "agent_feedback"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rating: Mapped[str] = mapped_column(String(8), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    eval_case_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eval_case_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )


__all__ = ["AgentFeedback", "FeedbackRating"]
